import * as path from 'path';
import * as fs from 'fs-extra';
import { parseSkillMd } from './utils';
import { runSingleQuery } from './run_eval';
import { improveDescription } from './improve_description';
import { generateHtml } from './generate_report';

interface EvalItem {
  query: string;
  should_trigger: boolean;
}

interface RunLoopOptions {
  evalSetPath: string;
  skillPath: string;
  maxIterations?: number;
  holdout?: number;
  cliCommand?: string;
  outputDir?: string;
}

/**
 * シャッフル処理
 */
function shuffle<T>(array: T[]): T[] {
  const arr = [...array];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/**
 * 評価データセットを学習用とテスト用に分割します。
 * トリガー可否 (should_trigger) の比率を保って分割します（層化抽出）。
 */
function splitEvalSet(evalSet: EvalItem[], holdout: number): [EvalItem[], EvalItem[]] {
  if (holdout <= 0 || holdout >= 1) {
    return [evalSet, []];
  }

  const triggers = evalSet.filter(e => e.should_trigger);
  const noTriggers = evalSet.filter(e => !e.should_trigger);

  const shuffledTriggers = shuffle(triggers);
  const shuffledNoTriggers = shuffle(noTriggers);

  const triggerTestCount = Math.max(1, Math.floor(triggers.length * holdout));
  const noTriggerTestCount = Math.max(1, Math.floor(noTriggers.length * holdout));

  const testSet = [
    ...shuffledTriggers.slice(0, triggerTestCount),
    ...shuffledNoTriggers.slice(0, noTriggerTestCount)
  ];

  const trainSet = [
    ...shuffledTriggers.slice(triggerTestCount),
    ...shuffledNoTriggers.slice(noTriggerTestCount)
  ];

  return [trainSet, testSet];
}

/**
 * 評価実行と説明文改善のループを回し、最適な説明文を見つけ出します。
 */
export async function runLoop(options: RunLoopOptions) {
  const maxIterations = options.maxIterations || 5;
  const holdout = options.holdout !== undefined ? options.holdout : 0.2;
  const cliCommand = options.cliCommand || process.env.SKILL_CLI_COMMAND || 'claude';
  
  const absoluteSkillPath = path.resolve(options.skillPath);
  const { name: skillName, description: originalDescription, body: skillBody } = await parseSkillMd(absoluteSkillPath);
  
  const evalSet: EvalItem[] = await fs.readJson(path.resolve(options.evalSetPath));
  
  // 学習・テスト分割
  const [trainSet, testSet] = splitEvalSet(evalSet, holdout);
  console.log(`データセット分割: 学習用 ${trainSet.length} 件, テスト用 ${testSet.length} 件 (ホールドアウト率=${holdout})`);

  const history: any[] = [];
  let currentDescription = originalDescription;
  let bestIterationIdx = -1;

  const workspaceDir = options.outputDir ? path.resolve(options.outputDir) : path.join(absoluteSkillPath, 'workspace');
  await fs.ensureDir(workspaceDir);

  const reportPath = path.join(workspaceDir, 'optimization_report.html');
  const resultsJsonPath = path.join(workspaceDir, 'optimization_results.json');

  for (let iter = 1; iter <= maxIterations; iter++) {
    console.log(`\n============================================================`);
    console.log(`試行 (Iteration) ${iter} / ${maxIterations}`);
    console.log(`現在の説明文: "${currentDescription}"`);
    console.log(`============================================================\n`);

    // 学習用とテスト用を一括で評価実行（並行処理）
    const allQueries = [...trainSet, ...testSet];
    console.log(`${allQueries.length} 件のクエリの評価を実行中...`);

    const queryResults = await Promise.all(
      allQueries.map(async (item) => {
        const triggered = await runSingleQuery(item.query, skillName, currentDescription, cliCommand);
        const passed = triggered === item.should_trigger;
        return {
          query: item.query,
          should_trigger: item.should_trigger,
          triggered,
          passed
        };
      })
    );

    // 結果の分割
    const trainResultsList = queryResults.slice(0, trainSet.length);
    const testResultsList = queryResults.slice(trainSet.length);

    const trainPassed = trainResultsList.filter(r => r.passed).length;
    const trainAccuracy = trainResultsList.length > 0 ? (trainPassed / trainResultsList.length) : 1;

    const testPassed = testResultsList.filter(r => r.passed).length;
    const testAccuracy = testResultsList.length > 0 ? (testPassed / testResultsList.length) : 0;

    const trainSummary = { passed: trainPassed, failed: trainResultsList.length - trainPassed, total: trainResultsList.length };
    const testSummary = testResultsList.length > 0 ? { passed: testPassed, failed: testResultsList.length - testPassed, total: testResultsList.length } : undefined;

    console.log(`結果 - 試行 #${iter}:`);
    console.log(`  学習用精度 (Train Accuracy): ${(trainAccuracy * 100).toFixed(1)}% (${trainPassed}/${trainResultsList.length})`);
    if (testResultsList.length > 0) {
      console.log(`  テスト用精度 (Test Accuracy): ${(testAccuracy * 100).toFixed(1)}% (${testPassed}/${testResultsList.length})`);
    }

    // 履歴オブジェクトの構築
    const attempt = {
      iteration: iter,
      description: currentDescription,
      train_results: trainResultsList,
      test_results: testResultsList.length > 0 ? testResultsList : undefined,
      train_accuracy: trainAccuracy,
      test_accuracy: testResultsList.length > 0 ? testAccuracy : undefined,
      is_best: false
    };

    history.push(attempt);

    // 中間レポートおよびJSONの保存
    const tempReportData = { skill_name: skillName, history };
    await fs.writeJson(resultsJsonPath, tempReportData, { spaces: 2 });
    await fs.writeFile(reportPath, generateHtml(tempReportData), 'utf8');
    console.log(`  -> レポートと途中経過データを保存しました。`);

    // すべてパスした場合の早期終了
    if (trainAccuracy === 1.0 && (testResultsList.length === 0 || testAccuracy === 1.0)) {
      console.log(`🎉 すべてのテストケースをクリアしました！最適化ループを早期終了します。`);
      break;
    }

    if (iter < maxIterations) {
      console.log(`\nエージェントによる説明文の改善指示を生成中...`);
      try {
        currentDescription = await improveDescription(
          skillName,
          skillBody,
          currentDescription,
          { results: trainResultsList, summary: trainSummary },
          history,
          cliCommand,
          testResultsList.length > 0 ? { results: testResultsList, summary: testSummary } : undefined
        );
      } catch (err: any) {
        console.error(`説明文の改善処理中にエラーが発生したため、ループを中断します:`, err.message);
        break;
      }
    }
  }

  // 最良のイテレーションの決定
  let maxTrainAcc = -1;
  let maxTestAcc = -1;
  
  for (let i = 0; i < history.length; i++) {
    const h = history[i];
    const testAcc = h.test_accuracy !== undefined ? h.test_accuracy : 0;
    
    // 学習用精度を最優先、タイブレークはテスト用精度、さらに同じなら最初の試行
    if (h.train_accuracy > maxTrainAcc || (h.train_accuracy === maxTrainAcc && testAcc > maxTestAcc)) {
      maxTrainAcc = h.train_accuracy;
      maxTestAcc = testAcc;
      bestIterationIdx = i;
    }
  }

  if (bestIterationIdx !== -1) {
    history[bestIterationIdx].is_best = true;
    const bestDescription = history[bestIterationIdx].description;
    console.log(`\n============================================================`);
    console.log(`🏆 最適化完了！`);
    console.log(`最良の試行: 試行 #${history[bestIterationIdx].iteration}`);
    console.log(`最高精度: 学習用精度 ${(maxTrainAcc * 100).toFixed(1)}%`);
    console.log(`推奨する説明文:\n  "${bestDescription}"`);
    console.log(`============================================================`);

    // 最終データの再書き出し
    const finalReportData = { skill_name: skillName, history };
    await fs.writeJson(resultsJsonPath, finalReportData, { spaces: 2 });
    await fs.writeFile(reportPath, generateHtml(finalReportData), 'utf8');
  }
}

// 直接実行時の処理
if (require.main === module) {
  const evalSetPath = process.argv[2];
  const skillPath = process.argv[3];
  
  if (!evalSetPath || !skillPath) {
    console.error('使用方法: npx tsx run_loop.ts <eval_set.jsonへのパス> <スキルディレクトリパス>');
    process.exit(1);
  }

  runLoop({
    evalSetPath,
    skillPath
  }).then(() => {
    process.exit(0);
  }).catch(err => {
    console.error('❌ ループ実行エラー:', err.message);
    process.exit(1);
  });
}
