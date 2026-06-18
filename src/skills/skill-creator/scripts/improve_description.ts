import * as path from 'path';
import * as fs from 'fs-extra';
import { spawn } from 'child_process';
import { parseSkillMd } from './utils';

/**
 * サブプロセスでエージェントCLIを実行し、説明文改善のプロンプトを処理して結果をテキストで返します。
 * @param prompt エージェントへの指示プロンプト
 * @param cliCommand 実行するコマンド（デフォルト: `claude`）
 */
async function callAgent(prompt: string, cliCommand: string = process.env.SKILL_CLI_COMMAND || 'claude'): Promise<string> {
  const env = { ...process.env };
  delete env.CLAUDECODE;

  let args: string[] = [];
  if (cliCommand === 'claude') {
    args = ['-p', '--output-format', 'text'];
  } else {
    // 汎用コマンド用のデフォルト設定
    args = [];
  }

  return await new Promise<string>((resolve, reject) => {
    const child = spawn(cliCommand, args, {
      env,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (data) => {
      stdout += data.toString('utf8');
    });

    child.stderr.on('data', (data) => {
      stderr += data.toString('utf8');
    });

    child.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`エージェントCLIがエラーコード ${code} で終了しました。 \nStderr: ${stderr}`));
      } else {
        resolve(stdout);
      }
    });

    child.on('error', (err) => {
      reject(new Error(`エージェントCLI (${cliCommand}) の起動エラー: ${err.message}`));
    });

    // 標準入力にプロンプトを流し込む
    child.stdin.write(prompt);
    child.stdin.end();
  });
}

/**
 * 評価結果と履歴を基に、エージェントを呼び出して説明文を改善（最適化）します。
 * @param skillName スキル名
 * @param skillBody SKILL.md の本文
 * @param currentDescription 現在の説明文
 * @param trainResults 学習用クエリの実行結果
 * @param history 過去の改善の試行履歴
 * @param cliCommand 実行コマンド
 * @param testResults テスト用クエリの実行結果
 */
export async function improveDescription(
  skillName: string,
  skillBody: string,
  currentDescription: string,
  trainResults: { results: any[]; summary: any },
  history: any[],
  cliCommand: string = process.env.SKILL_CLI_COMMAND || 'claude',
  testResults?: { results: any[]; summary: any }
): Promise<string> {
  
  // トリガー失敗（すべきなのにしなかった）
  const failedTriggers = trainResults.results.filter(r => r.should_trigger && !r.passed);
  // 誤検知（すべきでないのにしてしまった）
  const falseTriggers = trainResults.results.filter(r => !r.should_trigger && !r.passed);

  const trainScore = `${trainResults.summary.passed}/${trainResults.summary.total}`;
  let scoresSummary = `学習用 (Train): ${trainScore}`;

  if (testResults) {
    const testScore = `${testResults.summary.passed}/${testResults.summary.total}`;
    scoresSummary += `、テスト用 (Test): ${testScore}`;
  }

  // 日本語のプロンプトの構築
  let prompt = `あなたは、"${skillName}" という名前のエージェントスキルの説明文（YAMLフロントマターの description）を最適化しようとしています。

エージェントスキルは、エージェントに特定の指示やワークフローを拡張するためのものです。エージェントは、ユーザーから入力された指示文に対して、この「説明文 (description)」のみを見てスキルを読み込む（トリガーする）かどうかを判断します。
そのため、あなたの目標は「関連するクエリでは確実にトリガーされ、無関係なクエリではトリガーされない」ような、具体的で適切な説明文を記述することです。

現在の説明文:
<current_description>
"${currentDescription}"
</current_description>

現在のスコア (${scoresSummary}):
`;

  if (failedTriggers.length > 0) {
    prompt += '\n▼ トリガーすべきだったが、トリガーされなかったクエリ (トリガー漏れ):\n';
    for (const r of failedTriggers) {
      prompt += `  - "${r.query}"\n`;
    }
  }

  if (falseTriggers.length > 0) {
    prompt += '\n▼ トリガーすべきではないが、トリガーされてしまったクエリ (誤トリガー):\n';
    for (const r of falseTriggers) {
      prompt += `  - "${r.query}"\n`;
    }
  }

  if (history && history.length > 0) {
    prompt += '\n▼ 過去の試行履歴 (これらと類似した説明文は避け、構造的に異なるアプローチを試みてください):\n';
    for (const h of history) {
      prompt += `  - 精度: ${(h.train_accuracy * 100).toFixed(0)}% | "${h.description}"\n`;
    }
  }

  prompt += `
スキルの本文 (SKILL.md の指示内容):
<skill_body>
${skillBody}
</skill_body>

【指示】
上記の評価結果とスキルの動作内容を分析し、精度を最大化するための新しい説明文を考えてください。
特に、トリガー漏れを防ぐために、スキルが対応すべきキーワードや状況を明記し、誤トリガーを防ぐために適用外となる境界を明確にしてください。
生成した新しい説明文は、必ず単一のタグ \`<description>ここに説明文</description>\` で囲んで出力してください。説明文以外の文章はタグの外に出すか、出力しないでください。説明文自体は日本語で記述してください。
`;

  try {
    const rawOutput = await callAgent(prompt, cliCommand);
    const match = rawOutput.match(/<description>([\s\S]*?)<\/description>/);
    if (!match) {
      throw new Error(`エージェントの出力から <description> タグが検出できませんでした。\n出力内容:\n${rawOutput}`);
    }
    return match[1].trim();
  } catch (e: any) {
    console.error('説明文の最適化中にエラーが発生しました:', e.message);
    throw e;
  }
}
