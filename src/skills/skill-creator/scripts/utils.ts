import * as fs from 'fs-extra';
import * as path from 'path';
import * as yaml from 'js-yaml';

/**
 * SKILL.md のフロントマターを表現するインターフェース
 */
export interface SkillMetadata {
  name: string;
  description: string;
  [key: string]: any;
}

/**
 * SKILL.md を解析し、名前、説明、および本文を取得します。
 * @param skillPath スキルディレクトリへのパス
 */
export async function parseSkillMd(skillPath: string): Promise<{ name: string; description: string; body: string; fullContent: string }> {
  const skillMdPath = path.join(skillPath, 'SKILL.md');
  if (!(await fs.pathExists(skillMdPath))) {
    throw new Error(`SKILL.md が見つかりません: ${skillMdPath}`);
  }

  const content = await fs.readFile(skillMdPath, 'utf8');
  const frontmatterRegex = /^---\r?\n([\s\S]*?)\r?\n---/;
  const match = content.match(frontmatterRegex);

  if (!match) {
    throw new Error('SKILL.md に YAML フロントマター (--- で囲まれたセクション) が見つかりません。');
  }

  const yamlStr = match[1];
  const body = content.replace(frontmatterRegex, '').trim();

  let parsed: SkillMetadata;
  try {
    parsed = yaml.load(yamlStr) as SkillMetadata;
  } catch (e: any) {
    throw new Error(`YAML フロントマターの解析に失敗しました: ${e.message}`);
  }

  if (!parsed || typeof parsed !== 'object') {
    throw new Error('フロントマターの解析結果がオブジェクトではありません。');
  }

  if (!parsed.name) {
    throw new Error("フロントマターに 'name' が定義されていません。");
  }

  if (!parsed.description) {
    throw new Error("フロントマターに 'description' が定義されていません。");
  }

  return {
    name: parsed.name,
    description: parsed.description,
    body,
    fullContent: content
  };
}
