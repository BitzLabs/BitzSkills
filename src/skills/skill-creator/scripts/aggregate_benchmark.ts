import * as path from 'path';
import * as fs from 'fs-extra';

interface Stat {
  mean: number;
  stddev: number;
  min: number;
  max: number;
}

interface BenchmarkSummary {
  run_summary: {
    [config: string]: {
      pass_rate: Stat;
      time_seconds?: Stat;
      tokens?: Stat;
    };
    delta: {
      pass_rate: string;
      time_seconds?: string;
      tokens?: string;
    };
  };
  runs: Array<{
    configuration: string;
    run_number: number;
    eval_id: number;
    eval_name: string;
    result: {
      passed: number;
      total: number;
      pass_rate: number;
      time_seconds?: number;
      errors?: number;
      tokens?: number;
    };
    expectations?: Array<{
      text: string;
      passed: boolean;
      evidence?: string;
    }>;
  }>;
  notes: {
    skill_name?: string;
    timestamp: string;
    evals_run: string[];
    runs_per_configuration: number;
  };
}

/**
 * 数値配列の平均、標準偏差、最小値、最大値を計算します。
 */
function calculateStats(values: number[]): Stat {
  if (values.length === 0) {
    return { mean: 0.0, stddev: 0.0, min: 0.0, max: 0.0 };
  }

  const n = values.length;
  const sum = values.reduce((a, b) => a + b, 0);
  const mean = sum / n;

  let variance = 0;
  if (n > 1) {
    variance = values.reduce((acc, x) => acc + (x - mean) ** 2, 0) / (n - 1);
  }
  const stddev = Math.sqrt(variance);

  return {
    mean: Math.round(mean * 10000) / 10000,
    stddev: Math.round(stddev * 10000) / 10000,
    min: Math.min(...values),
    max: Math.max(...values)
  };
}

/**
 * ベンチマークディレクトリから各実行結果を集計します。
 * @param benchmarkDir ベンチマーク結果の格納先ディレクトリ
 */
export async function aggregateBenchmark(benchmarkDir: string): Promise<BenchmarkSummary> {
  const absBenchmarkDir = path.resolve(benchmarkDir);
  let searchDir = absBenchmarkDir;

  const runsSubdir = path.join(absBenchmarkDir, 'runs');
  if (await fs.pathExists(runsSubdir)) {
    searchDir = runsSubdir;
  }

  const evalDirs: string[] = [];
  const items = await fs.readdir(searchDir);
  for (const item of items) {
    const fullPath = path.join(searchDir, item);
    const stat = await fs.stat(fullPath);
    if (stat.isDirectory() && item.startsWith('eval-')) {
      evalDirs.push(item);
    }
  }

  if (evalDirs.length === 0) {
    throw new Error(`評価結果ディレクトリが見つかりません。対象パス: ${searchDir}`);
  }

  // ソート
  evalDirs.sort((a, b) => {
    const numA = parseInt(a.replace('eval-', '')) || 0;
    const numB = parseInt(b.replace('eval-', '')) || 0;
    return numA - numB;
  });

  const allRuns: BenchmarkSummary['runs'] = [];
  const configValues: { [config: string]: { passRates: number[]; times: number[]; tokens: number[] } } = {};
  const evalsRun = new Set<string>();

  for (let idx = 0; idx < evalDirs.length; idx++) {
    const evalDirName = evalDirs[idx];
    const evalPath = path.join(searchDir, evalDirName);

    let evalId = idx;
    let evalName = evalDirName;

    const metadataPath = path.join(evalPath, 'eval_metadata.json');
    if (await fs.pathExists(metadataPath)) {
      try {
        const metadata = await fs.readJson(metadataPath);
        evalId = metadata.eval_id !== undefined ? metadata.eval_id : idx;
        evalName = metadata.eval_name || evalDirName;
      } catch (e) {
        // デコード失敗時はフォールバック
      }
    }
    evalsRun.add(evalName);

    // ディレクトリ直下の構成名フォルダを探索 (with_skill, without_skill 等)
    const configDirs = await fs.readdir(evalPath);
    for (const configName of configDirs) {
      const configPath = path.join(evalPath, configName);
      const configStat = await fs.stat(configPath);
      if (!configStat.isDirectory()) continue;

      // run-N ディレクトリが存在するか確認
      const runDirs = (await fs.readdir(configPath)).filter(d => d.startsWith('run-'));
      if (runDirs.length === 0) continue;

      if (!configValues[configName]) {
        configValues[configName] = { passRates: [], times: [], tokens: [] };
      }

      for (const runDirName of runDirs) {
        const runPath = path.join(configPath, runDirName);
        const runNum = parseInt(runDirName.replace('run-', '')) || 0;

        const gradingFile = path.join(runPath, 'grading.json');
        const timingFile = path.join(runPath, 'timing.json');

        if (!(await fs.pathExists(gradingFile))) {
          continue;
        }

        try {
          const grading = await fs.readJson(gradingFile);
          
          let durationSeconds = 0;
          if (await fs.pathExists(timingFile)) {
            const timing = await fs.readJson(timingFile);
            durationSeconds = timing.total_duration_seconds || (timing.duration_ms / 1000) || 0;
          } else if (grading.timing) {
            durationSeconds = grading.timing.total_duration_seconds || 0;
          }

          let tokenCount = 0;
          if (grading.execution_metrics && grading.execution_metrics.total_tokens) {
            tokenCount = grading.execution_metrics.total_tokens;
          } else if (await fs.pathExists(timingFile)) {
            const timing = await fs.readJson(timingFile);
            tokenCount = timing.total_tokens || 0;
          }

          const passedCount = grading.summary?.passed || 0;
          const totalCount = grading.summary?.total || 1;
          const passRate = grading.summary?.pass_rate !== undefined ? grading.summary.pass_rate : (passedCount / totalCount);

          // 集計用配列に追加
          configValues[configName].passRates.push(passRate);
          if (durationSeconds > 0) configValues[configName].times.push(durationSeconds);
          if (tokenCount > 0) configValues[configName].tokens.push(tokenCount);

          allRuns.push({
            configuration: configName,
            run_number: runNum,
            eval_id: evalId,
            eval_name: evalName,
            result: {
              passed: passedCount,
              total: totalCount,
              pass_rate: passRate,
              time_seconds: durationSeconds > 0 ? durationSeconds : undefined,
              errors: grading.execution_metrics?.errors_encountered || 0,
              tokens: tokenCount > 0 ? tokenCount : undefined
            },
            expectations: grading.expectations
          });
        } catch (e: any) {
          console.warn(`警告: 結果の読み込み中にエラーが発生しました (${runPath}):`, e.message);
        }
      }
    }
  }

  // 構成ごとの集計値算出
  const runSummary: BenchmarkSummary['run_summary'] = {
    delta: { pass_rate: '—' }
  } as any;

  const configKeys = Object.keys(configValues).sort();
  for (const config of configKeys) {
    const passRateStat = calculateStats(configValues[config].passRates);
    const timeStat = configValues[config].times.length > 0 ? calculateStats(configValues[config].times) : undefined;
    const tokensStat = configValues[config].tokens.length > 0 ? calculateStats(configValues[config].tokens) : undefined;

    runSummary[config] = {
      pass_rate: passRateStat,
      time_seconds: timeStat,
      tokens: tokensStat
    };
  }

  // 差分 (Delta) の計算 (2つの主要構成がある場合)
  if (configKeys.length >= 2) {
    // 例: with_skill と without_skill、あるいは new_skill と old_skill
    // 新しい方 (通常アルファベット順の後者、または'new/with') から 古い方 ('old/without') を引く
    let primary = configKeys.find(c => c.includes('with') || c.includes('new')) || configKeys[0];
    let baseline = configKeys.find(c => c.includes('without') || c.includes('old')) || configKeys[1];
    
    // 順序が逆なら入れ替える
    if (primary === baseline) {
      primary = configKeys[0];
      baseline = configKeys[1];
    }

    const prDiff = runSummary[primary].pass_rate.mean - runSummary[baseline].pass_rate.mean;
    runSummary.delta.pass_rate = (prDiff >= 0 ? '+' : '') + Math.round(prDiff * 100) + '%';

    if (runSummary[primary].time_seconds && runSummary[baseline].time_seconds) {
      const timeDiff = runSummary[primary].time_seconds!.mean - runSummary[baseline].time_seconds!.mean;
      runSummary.delta.time_seconds = (timeDiff >= 0 ? '+' : '') + timeDiff.toFixed(1) + 's';
    }

    if (runSummary[primary].tokens && runSummary[baseline].tokens) {
      const tokenDiff = runSummary[primary].tokens!.mean - runSummary[baseline].tokens!.mean;
      runSummary.delta.tokens = (tokenDiff >= 0 ? '+' : '') + Math.round(tokenDiff);
    }
  }

  const timestamp = new Date().toISOString();
  
  // スキル名推測
  let guessedSkillName = 'Unknown';
  if (allRuns.length > 0) {
    guessedSkillName = path.basename(absBenchmarkDir).split('-')[0] || 'Unknown';
  }

  const summaryData: BenchmarkSummary = {
    run_summary: runSummary,
    runs: allRuns,
    notes: {
      skill_name: guessedSkillName,
      timestamp,
      evals_run: Array.from(evalsRun),
      runs_per_configuration: allRuns.length / (configKeys.length * evalsRun.size) || 1
    }
  };

  // benchmark.json の保存
  const outputJsonPath = path.join(absBenchmarkDir, 'benchmark.json');
  await fs.writeJson(outputJsonPath, summaryData, { spaces: 2 });

  // サマリーMarkdownの生成
  let markdown = `# ベンチマーク集計サマリー (Benchmark Summary)\n\n`;
  markdown += `- **スキル名**: ${guessedSkillName}\n`;
  markdown += `- **実行日時**: ${timestamp}\n`;
  markdown += `- **テストケース数**: ${evalsRun.size}\n\n`;
  markdown += `## 構成別結果サマリー\n\n`;
  markdown += `| 構成 | アサーション合格率 | 実行時間 (秒) | トークン数 |\n`;
  markdown += `| --- | --- | --- | --- |\n`;
  
  for (const config of configKeys) {
    const pr = runSummary[config].pass_rate;
    const time = runSummary[config].time_seconds;
    const tokens = runSummary[config].tokens;
    
    markdown += `| **${config}** | ${(pr.mean * 100).toFixed(0)}% ± ${(pr.stddev * 100).toFixed(0)}% | ${time ? `${time.mean.toFixed(1)}s ± ${time.stddev.toFixed(1)}s` : '—'} | ${tokens ? `${Math.round(tokens.mean)} ± ${Math.round(tokens.stddev)}` : '—'} |\n`;
  }
  
  if (configKeys.length >= 2) {
    markdown += `| **差分 (Delta)** | ${runSummary.delta.pass_rate} | ${runSummary.delta.time_seconds || '—'} | ${runSummary.delta.tokens || '—'} |\n`;
  }
  
  const outputMdPath = path.join(absBenchmarkDir, 'summary.md');
  await fs.writeFile(outputMdPath, markdown, 'utf8');

  return summaryData;
}

// 直接実行時の処理
if (require.main === module) {
  const benchmarkDir = process.argv[2];
  if (!benchmarkDir) {
    console.error('使用方法: npx tsx aggregate_benchmark.ts <ベンチマークディレクトリパス>');
    process.exit(1);
  }

  aggregateBenchmark(benchmarkDir).then(() => {
    console.log(`✅ ベンチマークの集計が完了しました。benchmark.json と summary.md を保存しました。`);
    process.exit(0);
  }).catch(err => {
    console.error('❌ 集計失敗:', err.message);
    process.exit(1);
  });
}
