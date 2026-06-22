import * as fs from 'fs-extra';
import * as path from 'path';
import * as readline from 'readline';

const DEST_DIR = path.join(__dirname, '..', '.agents', 'skills');

async function askQuestion(query: string): Promise<string> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  return new Promise((resolve) => rl.question(query, (ans) => {
    rl.close();
    resolve(ans);
  }));
}

async function uninstall() {
  console.log('--- Agent Skills アンインストール処理を開始します ---');

  if (!(await fs.pathExists(DEST_DIR))) {
    console.log('警告: インストール済みのスキルディレクトリが存在しません。');
    return;
  }

  // コマンドライン引数を取得
  const args = process.argv.slice(2);
  
  // フラグのチェック
  const force = args.includes('--force') || args.includes('-y') || args.includes('--yes');
  // フラグ以外の引数をスキル名として抽出
  const skillNames = args.filter(arg => !arg.startsWith('-'));

  if (skillNames.length > 0) {
    // 個別アンインストール
    for (const skillName of skillNames) {
      const skillDestPath = path.join(DEST_DIR, skillName);
      if (await fs.pathExists(skillDestPath)) {
        console.log(`[${skillName}] を削除しています...`);
        await fs.remove(skillDestPath);
        console.log(`  -> [${skillName}] のアンインストールに成功しました。`);
      } else {
        console.log(`警告: スキル [${skillName}] はインストールされていません。パス: ${skillDestPath}`);
      }
    }
  } else {
    // 一括アンインストール
    const items = await fs.readdir(DEST_DIR);
    const installedSkills = [];
    for (const item of items) {
      const itemPath = path.join(DEST_DIR, item);
      const stat = await fs.stat(itemPath);
      if (stat.isDirectory()) {
        installedSkills.push(item);
      }
    }

    if (installedSkills.length === 0) {
      console.log('インストール済みのスキルはありません。');
      return;
    }

    console.log('以下のインストール済みスキルがすべて削除されます:');
    installedSkills.forEach(s => console.log(`  - ${s}`));

    if (!force) {
      const answer = await askQuestion('\n本当にすべてのスキルをアンインストールしますか？ (y/N): ');
      if (answer.toLowerCase() !== 'y' && answer.toLowerCase() !== 'yes') {
        console.log('アンインストールはキャンセルされました。');
        return;
      }
    }

    console.log('\nすべてのスキルを削除しています...');
    for (const skillName of installedSkills) {
      const skillDestPath = path.join(DEST_DIR, skillName);
      await fs.remove(skillDestPath);
    }
    console.log('  -> すべてのスキルのアンインストールが完了しました！');
  }
}

uninstall().catch((err) => {
  console.error('予期しないエラーが発生しました:', err);
  process.exit(1);
});
