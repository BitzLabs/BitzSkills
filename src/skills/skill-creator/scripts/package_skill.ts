import * as path from 'path';
import * as fs from 'fs-extra';
import AdmZip from 'adm-zip';
import { validateSkill } from './quick_validate';

const EXCLUDE_DIRS = new Set(['__pycache__', 'node_modules', '.git']);
const EXCLUDE_FILES = new Set(['.DS_Store', 'thumbs.db']);
const EXCLUDE_GLOBS = [/\.pyc$/, /\.log$/];
const ROOT_EXCLUDE_DIRS = new Set(['evals', 'workspace']);

/**
 * 除外対象のファイルまたはディレクトリであるかを判定します。
 * @param relativePath スキルルートからの相対パス
 * @param isDir ディレクトリであるか
 */
function shouldExclude(relativePath: string, isDir: boolean): boolean {
  const parts = relativePath.split(path.sep);
  
  // ディレクトリ全体の除外確認
  if (parts.some(part => EXCLUDE_DIRS.has(part))) {
    return true;
  }

  // スキルルート直下の除外確認 (evals など)
  if (parts.length > 0 && ROOT_EXCLUDE_DIRS.has(parts[0])) {
    return true;
  }

  const name = parts[parts.length - 1];
  if (!isDir) {
    if (EXCLUDE_FILES.has(name)) {
      return true;
    }
    if (EXCLUDE_GLOBS.some(regex => regex.test(name))) {
      return true;
    }
  }

  return false;
}

/**
 * 指定されたスキルディレクトリを .skill (zip) ファイルにアーカイブします。
 * @param skillPath スキルディレクトリへのパス
 * @param outputDir 出力先ディレクトリ（省略時はスキルパスの親ディレクトリ）
 */
export async function packageSkill(skillPath: string, outputDir?: string): Promise<string> {
  const absoluteSkillPath = path.resolve(skillPath);
  
  // 1. パッケージ作成前にバリデーションを実行
  const validation = await validateSkill(absoluteSkillPath);
  if (!validation.success) {
    throw new Error(`スキルバリデーションエラー: ${validation.error}`);
  }

  const skillName = path.basename(absoluteSkillPath);
  const outDir = outputDir ? path.resolve(outputDir) : path.dirname(absoluteSkillPath);
  const outputFilePath = path.join(outDir, `${skillName}.skill`);

  await fs.ensureDir(outDir);

  const zip = new AdmZip();

  // 再帰的にファイルを探索してzipに追加
  async function addFilesRecursively(currentPath: string) {
    const items = await fs.readdir(currentPath);
    for (const item of items) {
      const fullPath = path.join(currentPath, item);
      const relPath = path.relative(absoluteSkillPath, fullPath);
      const stat = await fs.stat(fullPath);

      if (shouldExclude(relPath, stat.isDirectory())) {
        continue;
      }

      if (stat.isDirectory()) {
        await addFilesRecursively(fullPath);
      } else {
        // Zip 内のパスは常にフォワードスラッシュにする
        const zipPath = relPath.split(path.sep).join('/');
        zip.addLocalFile(fullPath, path.dirname(zipPath) === '.' ? '' : path.dirname(zipPath));
      }
    }
  }

  await addFilesRecursively(absoluteSkillPath);
  
  // ZIPファイル書き出し
  await new Promise<void>((resolve, reject) => {
    zip.writeZip(outputFilePath, (err) => {
      if (err) reject(err);
      else resolve();
    });
  });

  return outputFilePath;
}

// 直接実行時の処理
if (require.main === module) {
  const skillDir = process.argv[2];
  const customOut = process.argv[3];
  
  if (!skillDir) {
    console.error('使用方法: npx tsx package_skill.ts <スキルディレクトリへのパス> [出力ディレクトリ]');
    process.exit(1);
  }

  packageSkill(skillDir, customOut).then(filePath => {
    console.log(`✅ スキルパッケージが作成されました: ${filePath}`);
    process.exit(0);
  }).catch(err => {
    console.error('❌ パッケージ化に失敗しました:', err.message);
    process.exit(1);
  });
}
