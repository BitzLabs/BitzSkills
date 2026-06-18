import * as path from 'path';
import * as fs from 'fs-extra';
import { spawn } from 'child_process';
import { randomBytes } from 'crypto';
import { parseSkillMd } from './utils';

/**
 * プロジェクトのルートディレクトリを探索します。
 * .git または package.json が存在する位置を基準とします。
 */
function findProjectRoot(): string {
  let current = process.cwd();
  while (true) {
    if (fs.existsSync(path.join(current, 'package.json')) || fs.existsSync(path.join(current, '.git'))) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }
  return process.cwd();
}

/**
 * 1つのクエリを実行し、スキルがトリガーされたかを検証します。
 * @param query 実行プロンプト
 * @param skillName 評価対象のスキル名
 * @param skillDescription 評価対象の説明文
 * @param cliCommand 実行するエージェントCLIコマンド名
 * @param timeoutMs タイムアウト時間（ミリ秒）
 */
export async function runSingleQuery(
  query: string,
  skillName: string,
  skillDescription: string,
  cliCommand: string = process.env.SKILL_CLI_COMMAND || 'claude',
  timeoutMs: number = 30000
): Promise<boolean> {
  const projectRoot = findProjectRoot();
  const uniqueId = randomBytes(4).toString('hex');
  const tempSkillName = `${skillName}-skill-${uniqueId}`;
  
  // スキル配置先ディレクトリの特定
  // BitzSkills では .agents/skills/ 内で読み込まれます
  const agentsSkillsDir = path.join(projectRoot, '.agents', 'skills');
  const tempSkillDir = path.join(agentsSkillsDir, tempSkillName);
  const tempSkillMd = path.join(tempSkillDir, 'SKILL.md');

  // サブプロセスの環境変数。ネストした実行を防ぐCLAUDECODE環境変数を状況に応じて調整。
  const env = { ...process.env };
  delete env.CLAUDECODE;

  try {
    // 1. 一時スキルの作成
    await fs.ensureDir(tempSkillDir);
    const indentedDesc = skillDescription.split('\n').join('\n  ');
    const skillContent = `---
name: ${tempSkillName}
description: |
  ${indentedDesc}
---

# ${tempSkillName}
本スキルは検証用の一時スキルです: ${skillDescription}
`;
    await fs.writeFile(tempSkillMd, skillContent, 'utf8');

    // 2. 引数の構築（コマンドが claude の場合はストリーム JSON オプションを設定）
    let args: string[] = [];
    if (cliCommand === 'claude') {
      args = [
        '-p', query,
        '--output-format', 'stream-json',
        '--verbose',
        '--include-partial-messages'
      ];
    } else {
      // 汎用コマンド（antigravity等）の場合はプロンプトを直接渡すなど
      args = [query];
    }

    // 3. サブプロセスの実行
    return await new Promise<boolean>((resolve) => {
      const child = spawn(cliCommand, args, {
        cwd: projectRoot,
        env,
        stdio: ['ignore', 'pipe', 'pipe']
      });

      let triggered = false;
      let outputBuffer = '';
      
      const timeout = setTimeout(() => {
        child.kill();
        resolve(false);
      }, timeoutMs);

      child.stdout.on('data', (data) => {
        const chunk = data.toString('utf8');
        outputBuffer += chunk;

        // トリガー検知ロジック
        // A. JSON ストリームの解析 (claude コマンド用)
        if (cliCommand === 'claude') {
          // tool_use イベントや、一時スキル名の読み込みが発生しているかをチェック
          if (chunk.includes(tempSkillName)) {
            triggered = true;
            child.kill();
          }
        } else {
          // B. プレーンテキスト出力の解析
          // ログ等に一時スキル名が読み込まれた形跡があるかをチェック
          if (outputBuffer.includes(tempSkillName)) {
            triggered = true;
            child.kill();
          }
        }
      });

      child.stderr.on('data', (data) => {
        const chunk = data.toString('utf8');
        if (chunk.includes(tempSkillName)) {
          triggered = true;
          child.kill();
        }
      });

      child.on('close', () => {
        clearTimeout(timeout);
        // 最終的なバッファ確認
        if (outputBuffer.includes(tempSkillName)) {
          triggered = true;
        }
        resolve(triggered);
      });

      child.on('error', (err) => {
        console.error(`警告: コマンド ${cliCommand} の起動に失敗しました:`, err.message);
        clearTimeout(timeout);
        resolve(false);
      });
    });

  } finally {
    // 4. 一時スキルのクリーンアップ
    try {
      if (await fs.pathExists(tempSkillDir)) {
        await fs.remove(tempSkillDir);
      }
    } catch (e: any) {
      console.warn(`警告: 一時スキルディレクトリの削除に失敗しました (${tempSkillDir}):`, e.message);
    }
  }
}

// 直接実行時の処理
if (require.main === module) {
  const query = process.argv[2];
  const skillDir = process.argv[3];
  
  if (!query || !skillDir) {
    console.error('使用方法: npx tsx run_eval.ts "<検証クエリ>" <スキルディレクトリパス> [コマンド]');
    process.exit(1);
  }

  const customCommand = process.argv[4];

  parseSkillMd(skillDir).then(async ({ name, description }) => {
    console.log(`検証クエリ: "${query}" に対して "${name}" をトリガーするか検証中...`);
    const triggered = await runSingleQuery(query, name, description, customCommand);
    console.log(`結果: ${triggered ? '🎯 トリガーされました (Triggered)' : '❌ トリガーされませんでした (Not Triggered)'}`);
    process.exit(triggered ? 0 : 1);
  }).catch(err => {
    console.error('❌ エラー:', err.message);
    process.exit(1);
  });
}
