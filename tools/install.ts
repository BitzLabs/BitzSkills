import * as fs from 'fs-extra';
import * as path from 'path';
import * as yaml from 'js-yaml';

const SRC_DIR = path.join(__dirname, '..', 'src', 'skills');
const DEST_DIR = path.join(__dirname, '..', '.agents', 'skills');

interface SkillFrontmatter {
  name: string;
  description: string;
  [key: string]: any;
}

async function validateAndInstall() {
  console.log('--- Agent Skills インストール処理を開始します ---');

  if (!(await fs.pathExists(SRC_DIR))) {
    console.error(`エラー: ソースディレクトリが存在しません: ${SRC_DIR}`);
    process.exit(1);
  }

  // ソース配下のスキルディレクトリ一覧を取得
  const items = await fs.readdir(SRC_DIR);
  const skillDirs = [];
  for (const item of items) {
    const itemPath = path.join(SRC_DIR, item);
    const stat = await fs.stat(itemPath);
    if (stat.isDirectory()) {
      skillDirs.push(item);
    }
  }

  if (skillDirs.length === 0) {
    console.log('警告: インストール対象のスキルが見つかりませんでした。');
    return;
  }

  for (const skillName of skillDirs) {
    const skillSrcPath = path.join(SRC_DIR, skillName);
    const skillDestPath = path.join(DEST_DIR, skillName);
    const skillMdPath = path.join(skillSrcPath, 'SKILL.md');

    console.log(`\n[${skillName}] の検証とインストールを実行中...`);

    // 1. SKILL.md の存在確認
    if (!(await fs.pathExists(skillMdPath))) {
      console.error(`エラー: [${skillName}] 内に SKILL.md が見つかりません。パス: ${skillMdPath}`);
      process.exit(1);
    }

    const content = await fs.readFile(skillMdPath, 'utf8');

    // 2. YAMLフロントマターの抽出と検証
    const frontmatterRegex = /^---\r?\n([\s\S]*?)\r?\n---/;
    const match = content.match(frontmatterRegex);

    if (!match) {
      console.error(`エラー: [${skillName}] の SKILL.md に正しいYAMLフロントマター (--- で囲まれたセクション) がありません。`);
      process.exit(1);
    }

    const yamlStr = match[1];
    let parsed: SkillFrontmatter;
    try {
      parsed = yaml.load(yamlStr) as SkillFrontmatter;
    } catch (e: any) {
      console.error(`エラー: [${skillName}] の YAMLフロントマターの解析に失敗しました:`, e.message);
      process.exit(1);
    }

    if (!parsed || typeof parsed !== 'object') {
      console.error(`エラー: [${skillName}] の フロントマターがオブジェクトではありません。`);
      process.exit(1);
    }

    if (!parsed.name || typeof parsed.name !== 'string') {
      console.error(`エラー: [${skillName}] の フロントマターに有効な 'name' (string) が定義されていません。`);
      process.exit(1);
    }

    if (!parsed.description || typeof parsed.description !== 'string') {
      console.error(`エラー: [${skillName}] の フロントマターに有効な 'description' (string) が定義されていません。`);
      process.exit(1);
    }

    console.log(`  -> YAMLフロントマター検証完了: name="${parsed.name}"`);

    // 3. 500行制限チェック
    // フロントマター部分を除去した本文を抽出
    const bodyContent = content.replace(frontmatterRegex, '').trim();
    const bodyLines = bodyContent.split(/\r?\n/);
    const lineCount = bodyLines.length;

    if (lineCount > 500) {
      console.error(`エラー: [${skillName}] の SKILL.md 本文が制限の500行を超えています (現在の行数: ${lineCount}行)。`);
      console.error(`       詳細な仕様や資料は references/ サブディレクトリに分割してください。`);
      process.exit(1);
    }

    console.log(`  -> 500行制限チェック完了 (現在の本文行数: ${lineCount}行)`);

    // 4. インストール（ディレクトリコピー）
    try {
      // コピー先を一度クリア
      await fs.emptyDir(skillDestPath);
      // ソースをコピー
      await fs.copy(skillSrcPath, skillDestPath);
      console.log(`  -> インストール成功: ${skillDestPath}`);
    } catch (e: any) {
      console.error(`エラー: [${skillName}] のコピー処理中にエラーが発生しました:`, e.message);
      process.exit(1);
    }
  }

  console.log('\n--- すべてのスキルの検証およびインストールが正常に完了しました！ ---');
}

validateAndInstall().catch((err) => {
  console.error('予期しないエラーが発生しました:', err);
  process.exit(1);
});
