import * as path from 'path';
import * as fs from 'fs-extra';

interface ResultItem {
  query: string;
  should_trigger: boolean;
  triggered: boolean;
  passed: boolean;
}

interface Attempt {
  iteration: number;
  description: string;
  train_results: ResultItem[];
  test_results?: ResultItem[];
  train_accuracy: number;
  test_accuracy?: number;
  is_best?: boolean;
}

interface LoopData {
  skill_name: string;
  history: Attempt[];
  holdout_ratio?: number;
}

/**
 * データを HTML エンコードします。
 */
function escapeHtml(text: string): string {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * 説明文最適化の推移を示す HTML レポートを生成します。
 */
export function generateHtml(data: LoopData, autoRefresh: boolean = false): string {
  const history = data.history || [];
  const skillName = data.skill_name || 'Unknown';
  
  let trainQueries: Array<{ query: string; should_trigger: boolean }> = [];
  let testQueries: Array<{ query: string; should_trigger: boolean }> = [];

  if (history.length > 0) {
    const first = history[0];
    trainQueries = (first.train_results || []).map(r => ({
      query: r.query,
      should_trigger: r.should_trigger !== undefined ? r.should_trigger : true
    }));
    testQueries = (first.test_results || []).map(r => ({
      query: r.query,
      should_trigger: r.should_trigger !== undefined ? r.should_trigger : true
    }));
  }

  const bestAttempt = history.find(h => h.is_best) || history[history.length - 1];

  let html = `<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  ${autoRefresh ? '<meta http-equiv="refresh" content="5">' : ''}
  <title>${escapeHtml(skillName)} - スキル説明文最適化レポート</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600&family=Lora:wght@400;500&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Lora', Georgia, serif;
      padding: 2rem;
      background: #faf9f5;
      color: #141413;
      margin: 0;
    }
    h1 { font-family: 'Poppins', sans-serif; color: #141413; font-size: 1.75rem; margin-bottom: 0.5rem; }
    .explainer {
      background: white;
      padding: 1rem;
      border-radius: 6px;
      margin-bottom: 1.5rem;
      border: 1px solid #e8e6dc;
      color: #b0aea5;
      font-size: 0.85rem;
      line-height: 1.6;
    }
    .summary {
      background: white;
      padding: 1.25rem;
      border-radius: 6px;
      margin-bottom: 1.5rem;
      border: 1px solid #e8e6dc;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .summary h2 { font-family: 'Poppins', sans-serif; font-size: 1.1rem; margin-bottom: 0.75rem; }
    .summary p { margin: 0.25rem 0; font-size: 0.9rem; }
    .best-desc {
      background: #f4f6f2;
      border-left: 4px solid #788c5d;
      padding: 0.75rem 1rem;
      margin-top: 0.75rem;
      font-family: monospace;
      white-space: pre-wrap;
      font-size: 0.8rem;
    }
    .table-container {
      overflow-x: auto;
      width: 100%;
      background: white;
      border: 1px solid #e8e6dc;
      border-radius: 6px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    table {
      border-collapse: collapse;
      font-size: 0.75rem;
      width: 100%;
    }
    th, td {
      padding: 0.6rem 0.75rem;
      text-align: left;
      border: 1px solid #e8e6dc;
    }
    th {
      font-family: 'Poppins', sans-serif;
      background: #141413;
      color: #faf9f5;
      font-weight: 500;
    }
    th.test-col {
      background: #6a9bcc;
    }
    th.iter-col {
      text-align: center;
      min-width: 80px;
    }
    td.iter-cell {
      text-align: center;
      font-weight: 600;
    }
    .pass { color: #788c5d; font-weight: bold; font-size: 1rem; text-align: center; }
    .fail { color: #c44; font-weight: bold; font-size: 1rem; text-align: center; }
    .type-header {
      background: #e8e6dc;
      font-family: 'Poppins', sans-serif;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 0.7rem;
      color: #141413;
    }
    .desc-row {
      background: #fdfdfb;
    }
  </style>
</head>
<body>
  <h1>説明文最適化レポート: ${escapeHtml(skillName)}</h1>
  <div class="explainer">
    このレポートは、エージェントスキルの説明文（メタデータ description）が評価用プロンプト群に対して適切にトリガーされるかを繰り返しシミュレーションし、最適化していく推移をまとめたものです。
  </div>`;

  if (bestAttempt) {
    html += `
  <div class="summary">
    <h2>最適化サマリー</h2>
    <p><strong>総試行回数 (Iterations)</strong>: ${history.length}</p>
    <p><strong>最良の試行</strong>: 試行 #${bestAttempt.iteration} (学習用精度: ${(bestAttempt.train_accuracy * 100).toFixed(0)}%${bestAttempt.test_accuracy !== undefined ? `、テスト用精度: ${(bestAttempt.test_accuracy * 100).toFixed(0)}%` : ''})</p>
    <p><strong>最良の説明文 (Best Description)</strong>:</p>
    <div class="best-desc">${escapeHtml(bestAttempt.description)}</div>
  </div>`;
  }

  html += `
  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th style="width: 35%;">評価用クエリ</th>
          <th style="width: 10%;">期待トリガー</th>`;

  // 各イテレーションのカラムヘッダーを追加
  for (const att of history) {
    const isBest = att.is_best ? ' 👑' : '';
    html += `
          <th class="iter-col ${att.is_best ? 'test-col' : ''}">試行 #${att.iteration}${isBest}<br>
            <span style="font-size: 0.65rem; font-weight: normal;">
              学習: ${(att.train_accuracy * 100).toFixed(0)}%
              ${att.test_accuracy !== undefined ? `<br>テスト: ${(att.test_accuracy * 100).toFixed(0)}%` : ''}
            </span>
          </th>`;
  }

  html += `
        </tr>
      </thead>
      <tbody>`;

  // 1. 学習用クエリの行をレンダリング
  if (trainQueries.length > 0) {
    html += `
        <tr>
          <td colspan="${2 + history.length}" class="type-header">学習用クエリ (Train Set)</td>
        </tr>`;

    for (let qi = 0; qi < trainQueries.length; qi++) {
      const q = trainQueries[qi];
      html += `
        <tr>
          <td>${escapeHtml(q.query)}</td>
          <td>${q.should_trigger ? 'ON' : 'OFF'}</td>`;
      for (const att of history) {
        const res = att.train_results[qi];
        const passed = res ? res.passed : false;
        html += `<td class="${passed ? 'pass' : 'fail'}">${passed ? '✓' : '✗'}</td>`;
      }
      html += `
        </tr>`;
    }
  }

  // 2. テスト用クエリの行をレンダリング
  if (testQueries.length > 0) {
    html += `
        <tr>
          <td colspan="${2 + history.length}" class="type-header">評価用クエリ (Test Set)</td>
        </tr>`;

    for (let qi = 0; qi < testQueries.length; qi++) {
      const q = testQueries[qi];
      html += `
        <tr>
          <td>${escapeHtml(q.query)}</td>
          <td>${q.should_trigger ? 'ON' : 'OFF'}</td>`;
      for (const att of history) {
        const res = att.test_results ? att.test_results[qi] : null;
        const passed = res ? res.passed : false;
        html += `<td class="${passed ? 'pass' : 'fail'}">${passed ? '✓' : '✗'}</td>`;
      }
      html += `
        </tr>`;
    }
  }

  // 3. 説明文自体の行をレンダリング
  html += `
        <tr class="desc-row">
          <td colspan="2" style="font-weight: bold; background: #e8e6dc;">各試行の説明文</td>`;
  for (const att of history) {
    html += `
          <td style="vertical-align: top; font-family: monospace; font-size: 0.65rem; background: #faf9f5; white-space: pre-wrap; word-break: break-all;">${escapeHtml(att.description)}</td>`;
  }
  html += `
        </tr>`;

  html += `
      </tbody>
    </table>
  </div>
</body>
</html>`;

  return html;
}

// 直接実行時の処理
if (require.main === module) {
  const jsonPathArg = process.argv[2];
  const outHtmlPathArg = process.argv[3];
  
  if (!jsonPathArg) {
    console.error('使用方法: npx tsx generate_report.ts <results.jsonへのパス> [出力HTMLのパス]');
    process.exit(1);
  }

  const absJsonPath = path.resolve(jsonPathArg);
  const absHtmlPath = outHtmlPathArg ? path.resolve(outHtmlPathArg) : path.join(path.dirname(absJsonPath), 'optimization_report.html');

  fs.readJson(absJsonPath).then(data => {
    const htmlContent = generateHtml(data);
    return fs.writeFile(absHtmlPath, htmlContent, 'utf8');
  }).then(() => {
    console.log(`✅ レポートを書き出しました: ${absHtmlPath}`);
    process.exit(0);
  }).catch(err => {
    console.error('❌ レポート生成に失敗しました:', err.message);
    process.exit(1);
  });
}
