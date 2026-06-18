import * as path from 'path';
import * as fs from 'fs-extra';
import { parseSkillMd } from './utils';

const ALLOWED_PROPERTIES = new Set(['name', 'description', 'license', 'allowed-tools', 'metadata', 'compatibility']);

/**
 * 単一のスキルディレクトリの構造とメタデータを検証します。
 * @param skillPath スキルのディレクトリパス
 */
export async function validateSkill(skillPath: string): Promise<{ success: boolean; error?: string }> {
  try {
    const skillMdPath = path.join(skillPath, 'SKILL.md');
    if (!(await fs.pathExists(skillMdPath))) {
      return { success: false, error: 'SKILL.md が見つかりません。' };
    }

    const { name, description, body, fullContent } = await parseSkillMd(skillPath);

    // 1. スキル名の検証 (kebab-case)
    const kebabCaseRegex = /^[a-z0-9-]+$/;
    if (!kebabCaseRegex.test(name)) {
      return { success: false, error: `スキル名 "${name}" が kebab-case (英小文字、数字、ハイフンのみ) ではありません。` };
    }

    // 2. ディレクトリ名と定義されたスキル名の一致確認
    const dirName = path.basename(skillPath);
    if (dirName !== name) {
      return { success: false, error: `ディレクトリ名 "${dirName}" と SKILL.md 内の name "${name}" が一致していません。` };
    }

    // 3. フロントマターの想定外のキーの確認
    const frontmatterRegex = /^---\r?\n([\s\S]*?)\r?\n---/;
    const match = fullContent.match(frontmatterRegex);
    if (match) {
      const yaml = require('js-yaml');
      const parsed = yaml.load(match[1]) as any;
      const extraKeys = Object.keys(parsed).filter(key => !ALLOWED_PROPERTIES.has(key));
      if (extraKeys.length > 0) {
        return { success: false, error: `フロントマターに未定義のプロパティが含まれています: ${extraKeys.join(', ')}` };
      }
    }

    // 4. 説明文の検証
    if (description.trim().length < 10) {
      return { success: false, error: '説明文 (description) が短すぎます。より具体的なトリガー条件を記述してください。' };
    }

    // 5. 行数制限の検証 (500行制限)
    const lines = body.split(/\r?\n/);
    const lineCount = lines.length;
    if (lineCount > 500) {
      return { success: false, error: `SKILL.md 本文の行数 (${lineCount} 行) が 500 行を超えています。詳細な仕様は references/ ディレクトリへ移行してください。` };
    }

    return { success: true };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}

// 直接実行時の処理
if (require.main === module) {
  const targetDir = process.argv[2];
  if (!targetDir) {
    console.error('使用方法: npx tsx quick_validate.ts <スキルディレクトリへのパス>');
    process.exit(1);
  }

  const absolutePath = path.resolve(targetDir);
  validateSkill(absolutePath).then(result => {
    if (result.success) {
      console.log(`✅ スキル検証成功: ${absolutePath}`);
      process.exit(0);
    } else {
      console.error(`❌ スキル検証失敗: ${result.error}`);
      process.exit(1);
    }
  }).catch(err => {
    console.error('予期しない検証エラー:', err);
    process.exit(1);
  });
}
