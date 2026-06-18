import * as path from 'path';
import * as fs from 'fs-extra';
import * as http from 'http';
import { exec } from 'child_process';
import { parseSkillMd } from '../scripts/utils';

// 無視するメタデータファイル
const METADATA_FILES = new Set(['transcript.md', 'user_notes.md', 'metrics.json', 'grading.json', 'timing.json', 'eval_metadata.json']);

// テキストとしてインライン描画する拡張子
const TEXT_EXTENSIONS = new Set([
  '.txt', '.md', '.json', '.csv', '.py', '.js', '.ts', '.tsx', '.jsx',
  '.yaml', '.yml', '.xml', '.html', '.css', '.sh', '.rb', '.go', '.rs',
  '.java', '.c', '.cpp', '.h', '.hpp', '.sql', '.r', '.toml'
]);

// 画像としてインライン表示する拡張子
const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']);

// MIMEタイプのカスタムマップ
const MIME_MAP: { [ext: string]: string } = {
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.pdf': 'application/pdf',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '.csv': 'text/csv',
  '.json': 'application/json',
  '.txt': 'text/plain',
  '.html': 'text/html',
  '.md': 'text/markdown'
};

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  return MIME_MAP[ext] || 'application/octet-stream';
}

interface FilePayload {
  name: string;
  type: 'text' | 'image' | 'pdf' | 'xlsx' | 'binary' | 'error';
  content?: string;
  data_uri?: string;
  data_b64?: string;
}

/**
 * ファイルのコンテンツをエンコードまたは読み込みます。
 */
async function embedFile(filePath: string): Promise<FilePayload> {
  const name = path.basename(filePath);
  const ext = path.extname(filePath).toLowerCase();
  const mime = getMimeType(filePath);

  if (TEXT_EXTENSIONS.has(ext)) {
    const content = await fs.readFile(filePath, 'utf8');
    return { name, type: 'text', content };
  } else if (IMAGE_EXTENSIONS.has(ext) || ext === '.pdf') {
    const data = await fs.readFile(filePath);
    const b64 = data.toString('base64');
    const type = ext === '.pdf' ? 'pdf' : 'image';
    return { name, type, data_uri: `data:${mime};base64,${b64}` };
  } else if (ext === '.xlsx') {
    const data = await fs.readFile(filePath);
    const b64 = data.toString('base64');
    return { name, type: 'xlsx', data_b64: b64 };
  } else {
    // 汎用バイナリ
    const data = await fs.readFile(filePath);
    const b64 = data.toString('base64');
    return { name, type: 'binary', data_uri: `data:${mime};base64,${b64}` };
  }
}

interface RunPayload {
  id: string;
  prompt: string;
  eval_id?: number;
  outputs: FilePayload[];
  grading?: any;
}

/**
 * 出力ディレクトリを持つ各実行フォルダを走査・解析します。
 */
async function buildRun(workspaceRoot: string, runDir: string): Promise<RunPayload | null> {
  let prompt = '';
  let evalId: number | undefined;

  // 1. eval_metadata.json からプロンプトを取得
  const metadataCandidates = [
    path.join(runDir, 'eval_metadata.json'),
    path.join(path.dirname(runDir), 'eval_metadata.json')
  ];

  for (const candidate of metadataCandidates) {
    if (await fs.pathExists(candidate)) {
      try {
        const metadata = await fs.readJson(candidate);
        prompt = metadata.prompt || '';
        evalId = metadata.eval_id;
      } catch (e) {}
      if (prompt) break;
    }
  }

  // 2. transcript.md からフォールバック抽出
  if (!prompt) {
    const transcriptCandidates = [
      path.join(runDir, 'transcript.md'),
      path.join(runDir, 'outputs', 'transcript.md')
    ];
    for (const candidate of transcriptCandidates) {
      if (await fs.pathExists(candidate)) {
        try {
          const text = await fs.readFile(candidate, 'utf8');
          const match = text.match(/## 実行プロンプト\r?\n\r?\n([\s\S]*?)(?=\r?\n##|$)/) || 
                        text.match(/## Eval Prompt\r?\n\r?\n([\s\S]*?)(?=\r?\n##|$)/);
          if (match) {
            prompt = match[1].trim();
          }
        } catch (e) {}
        if (prompt) break;
      }
    }
  }

  if (!prompt) {
    prompt = '(プロンプトが見つかりませんでした)';
  }

  const runId = path.relative(workspaceRoot, runDir).replace(/\//g, '-').replace(/\\/g, '-');

  // 出力ファイルの収集
  const outputsDir = path.join(runDir, 'outputs');
  const outputs: FilePayload[] = [];
  if (await fs.pathExists(outputsDir)) {
    const files = await fs.readdir(outputsDir);
    for (const file of files) {
      const filePath = path.join(outputsDir, file);
      const fileStat = await fs.stat(filePath);
      if (fileStat.isFile() && !METADATA_FILES.has(file)) {
        try {
          outputs.push(await embedFile(filePath));
        } catch (err: any) {
          outputs.push({
            name: file,
            type: 'error',
            content: `ファイルの読み込みエラー: ${err.message}`
          });
        }
      }
    }
  }

  // grading.json の読み込み
  let grading: any = undefined;
  const gradingCandidates = [
    path.join(runDir, 'grading.json'),
    path.join(path.dirname(runDir), 'grading.json')
  ];
  for (const candidate of gradingCandidates) {
    if (await fs.pathExists(candidate)) {
      try {
        grading = await fs.readJson(candidate);
      } catch (e) {}
      if (grading) break;
    }
  }

  return {
    id: runId,
    prompt,
    eval_id: evalId,
    outputs
  };
}

/**
 * 再帰的に実行ディレクトリ（outputsサブディレクトリを持つフォルダ）を探索します。
 */
async function findRunsRecursive(workspaceRoot: string, currentDir: string, runs: RunPayload[]) {
  const items = await fs.readdir(currentDir);
  
  // outputs フォルダが存在すれば実行フォルダと見なす
  if (items.includes('outputs')) {
    const run = await buildRun(workspaceRoot, currentDir);
    if (run) runs.push(run);
    return;
  }

  const skip = new Set(['node_modules', '.git', '__pycache__', 'skill', 'inputs']);
  for (const item of items) {
    const fullPath = path.join(currentDir, item);
    const itemStat = await fs.stat(fullPath);
    if (itemStat.isDirectory() && !skip.has(item)) {
      await findRunsRecursive(workspaceRoot, fullPath, runs);
    }
  }
}

/**
 * サーバーを起動してレビュー画面を提供します。
 */
async function serveReview(workspacePath: string, port: number, skillName: string, previousFeedbackPath?: string) {
  const absWorkspace = path.resolve(workspacePath);
  console.log(`ワークスペースの実行データを探索中: ${absWorkspace}`);

  const runs: RunPayload[] = [];
  if (await fs.pathExists(absWorkspace)) {
    await findRunsRecursive(absWorkspace, absWorkspace, runs);
  }
  
  // eval_id と id 順でソート
  runs.sort((a, b) => {
    const idA = a.eval_id !== undefined ? a.eval_id : Infinity;
    const idB = b.eval_id !== undefined ? b.eval_id : Infinity;
    if (idA !== idB) return idA - idB;
    return a.id.localeCompare(b.id);
  });

  console.log(`検出された実行数: ${runs.length} 件`);

  // ベンチマークデータの読み込み
  let benchmark: any = null;
  const benchmarkPath = path.join(absWorkspace, 'benchmark.json');
  if (await fs.pathExists(benchmarkPath)) {
    try {
      benchmark = await fs.readJson(benchmarkPath);
    } catch (e) {}
  }

  // 以前のフィードバックデータのロード
  let previousFeedback: any = {};
  if (previousFeedbackPath && await fs.pathExists(previousFeedbackPath)) {
    try {
      const data = await fs.readJson(previousFeedbackPath);
      if (data.reviews) {
        for (const rev of data.reviews) {
          previousFeedback[rev.run_id] = rev.feedback;
        }
      }
    } catch (e) {}
  }

  // クライアントに渡す埋め込み用オブジェクト
  const embeddedData = {
    skill_name: skillName,
    runs,
    benchmark,
    previous_feedback: previousFeedback
  };

  const viewerHtmlPath = path.join(__dirname, 'viewer.html');
  if (!(await fs.pathExists(viewerHtmlPath))) {
    throw new Error(`viewer.html テンプレートが見つかりません: ${viewerHtmlPath}`);
  }

  const rawHtml = await fs.readFile(viewerHtmlPath, 'utf8');
  // プレースホルダーの置換
  const finalHtml = rawHtml.replace('/*__EMBEDDED_DATA__*/', `const EMBEDDED_DATA = ${JSON.stringify(embeddedData)};`);

  const feedbackJsonPath = path.join(absWorkspace, 'feedback.json');

  // HTTPサーバーの定義
  const server = http.createServer((req, res) => {
    const url = req.url || '/';

    if (req.method === 'GET' && url === '/') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(finalHtml);
    } else if (req.method === 'GET' && url === '/api/feedback') {
      fs.readJson(feedbackJsonPath)
        .then(data => {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(data));
        })
        .catch(() => {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ reviews: [], status: 'empty' }));
        });
    } else if (req.method === 'POST' && url === '/api/feedback') {
      let body = '';
      req.on('data', chunk => {
        body += chunk.toString();
      });
      req.on('end', () => {
        fs.writeJson(feedbackJsonPath, JSON.parse(body), { spaces: 2 })
          .then(() => {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true }));
          })
          .catch(err => {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: err.message }));
          });
      });
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    }
  });

  server.listen(port, () => {
    const url = `http://localhost:${port}`;
    console.log(`\n============================================================`);
    console.log(`Reviewer dashboard is running at: ${url}`);
    console.log(`レビュー結果は ${feedbackJsonPath} に保存されます。`);
    console.log(`レビューを完了し、確定ボタンを押した後に CLI に戻ってください。`);
    console.log(`============================================================\n`);

    // 自動でブラウザを起動 (Windows用)
    exec(`cmd.exe /c start ${url}`);
  });
}

// 直接実行時の処理
if (require.main === module) {
  const workspacePath = process.argv[2];
  if (!workspacePath) {
    console.error('使用方法: npx tsx generate_review.ts <ワークスペースパス> [--port ポート番号] [--skill-name スキル名]');
    process.exit(1);
  }

  // 簡易引数パース
  const args = process.argv.slice(3);
  let port = 3000;
  let skillName = path.basename(path.resolve(workspacePath)).split('-')[0] || 'MySkill';
  let prevFeedback: string | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--port' && args[i+1]) {
      port = parseInt(args[i+1]) || 3000;
    }
    if (args[i] === '--skill-name' && args[i+1]) {
      skillName = args[i+1];
    }
    if (args[i] === '--previous-feedback' && args[i+1]) {
      prevFeedback = args[i+1];
    }
  }

  serveReview(workspacePath, port, skillName, prevFeedback).catch(err => {
    console.error('❌ サーバーエラー:', err.message);
    process.exit(1);
  });
}
