"""失敗を結果として残す公開行列の調査用台帳。旧台帳と停止原は変更しない。"""
from pathlib import Path
import re

import production_matrix_ledger as matrix

io = matrix.io
require = matrix.require
VERSION = 'public-matrix-survey-policy-0.1.0'
LOCAL_REJECTIONS = frozenset({'primary-capture-rejected', 'independent-capture-failed',
    'parent-original-verification-failed', 'independent-safety-or-integrity-unresolved'})
FAILURE_PHASES = {'primary', 'independent', 'parent'}
STATUSES = {'measured_correct', 'measured_incorrect', 'evaluation_failed'}


class SurveyLedger(matrix.MatrixLedger):
    """失敗枠を閉じて次へ進む。正常測定・失敗・未着手を混同しない。"""
    def __init__(self, storage, repository, bound, policy_raw):
        super().__init__(storage, repository, bound)
        try:
            require(bound.contract['version'] == matrix.SURVEY_VERSION
                and io.sha(policy_raw) == bound.contract['surveyPolicySha256'], 'survey policy pin')
            policy = matrix.strict_json(policy_raw)
            require(isinstance(policy, dict) and set(policy) == {'version', 'sourceCommit', 'campaignId',
                'startOrdinal', 'baselineSourceCommit', 'baselineCampaignId', 'baselineReport',
                'priorSlots', 'productResources', 'baselineExecution', 'baselineInputContract',
                'baselineDeployment', 'baselineSnapshotManifest'}, 'survey policy inventory')
            require(policy['version'] == VERSION and policy['sourceCommit'] == bound.contract['sourceCommit']
                and policy['campaignId'] == bound.contract['campaignId']
                and type(policy['startOrdinal']) is int and 1 <= policy['startOrdinal'] <= 92,
                'survey policy identity')
            self.policy, self.policy_raw = policy, policy_raw
            self.first = policy['startOrdinal']
            resources = policy['productResources']
            require(isinstance(resources, dict) and resources and all(isinstance(n, str)
                and n.startswith('resources/') and '..' not in Path(n).parts for n in resources),
                'survey product resource names')
            for digest in resources.values():io.pin(digest)
            require(isinstance(policy['priorSlots'], list) and len(policy['priorSlots']) == self.first-1,
                'survey prior coverage inventory')
            self.prior = []
            baseline_condition = None
            if policy['priorSlots']:
                old_execution = self.reference(policy['baselineExecution'])
                old_input = self.reference(policy['baselineInputContract'])
                old_bound = matrix.bind(old_execution, old_input,
                    **dict(zip(matrix.inputs.INPUT_NAMES, bound.raw_inputs)))
                require(old_bound.contract['sourceCommit'] == policy['baselineSourceCommit']
                    and old_bound.contract['campaignId'] == policy['baselineCampaignId'], 'survey baseline execution identity')
                from production_matrix_capture import condition_sha256
                old_deployment = self.reference(policy['baselineDeployment'])
                baseline_condition = condition_sha256(old_bound, old_deployment)
                old_manifest_raw = self.reference(policy['baselineSnapshotManifest'])
                old_manifest = matrix.strict_json(old_manifest_raw)
                require(io.sha(old_manifest_raw) == old_bound.contract['pins']['snapshotManifest']
                    and old_manifest.get('sourceCommit') == policy['baselineSourceCommit']
                    and old_manifest.get('resources') == resources
                    and len(resources) == matrix.strict_json(old_deployment)['snapshotResourceCount'],
                    'survey baseline product resources changed')
                require(all(old_bound.slot(n)['payloadSha256'] == bound.slot(n)['payloadSha256']
                    for n in range(1, 93)), 'survey baseline payloads changed')
            for ordinal, item in enumerate(policy['priorSlots'], 1):
                require(isinstance(item, dict) and set(item) == {'ordinal', 'status', 'reference'}
                    and type(item['ordinal']) is int and item['ordinal'] == ordinal
                    and item['status'] in STATUSES, 'survey prior slot identity')
                value = matrix.strict_json(self.reference(item['reference']))
                require(value['sourceCommit'] == policy['baselineSourceCommit']
                    and value['campaignId'] == policy['baselineCampaignId']
                    and value['conditionSha256'] == baseline_condition
                    and type(value['ordinal']) is int and value['ordinal'] == ordinal
                    and value['caseId'] == bound.slot(ordinal)['caseId']
                    and value['repetition'] == bound.slot(ordinal)['repetition'], 'survey prior original identity')
                parent = value.get('parent') or {}
                if item['status'] == 'evaluation_failed':
                    require(value.get('errorType') is not None and parent.get('ledgerFinalized') is not True,
                        'survey prior failed result')
                else:
                    require(value.get('errorType') is None and parent.get('ledgerFinalized') is True
                        and parent.get('proposedLedgerStatus') == item['status'], 'survey prior measured result')
                self.prior.append(value)
            if self.prior:
                baseline = matrix.strict_json(self.reference(policy['baselineReport']))
                require(baseline['sourceCommit'] == policy['baselineSourceCommit']
                    and baseline['campaignId'] == policy['baselineCampaignId']
                    and baseline['primaryReserved'] == self.first-1
                    and baseline['measuredCorrect'] == sum(x['status'] == 'measured_correct' for x in policy['priorSlots'])
                    and baseline['measuredIncorrect'] == sum(x['status'] == 'measured_incorrect' for x in policy['priorSlots'])
                    and baseline['failedSlots'] == sum(x['status'] == 'evaluation_failed' for x in policy['priorSlots']),
                    'survey baseline coverage binding')
            else:
                require(policy['baselineReport'] is None and policy['baselineSourceCommit'] is None
                    and policy['baselineCampaignId'] is None and all(policy[n] is None for n in
                        ['baselineExecution', 'baselineInputContract', 'baselineDeployment', 'baselineSnapshotManifest']),
                    'survey empty baseline')
        except Exception as exc:
            self.abort(None, 'survey-policy-rejected', type(exc).__name__)
            raise

    def reference(self, value, *, expected_path=None):
        require(isinstance(value, dict) and set(value) == {'relativePath', 'sha256'}, 'survey original reference')
        relative = value['relativePath']
        require(isinstance(relative, str) and re.fullmatch(r'[a-zA-Z0-9./_-]+', relative) is not None,
            'survey reference name')
        path = Path(relative)
        require(not path.is_absolute() and relative == path.as_posix() and path.parts[0] in {'.venv', 'evals'}
            and not set(path.parts) & {'..', '.git', 'auth.json', '.env', '.credentials.json', 'heldout',
                'codex-home', 'logs', 'state'} and (expected_path is None or path == expected_path),
            'survey reference boundary')
        raw = io.read_regular(self.repository/path)
        require(io.sha(raw) == io.pin(value['sha256']), 'survey referenced original drift')
        return raw

    def initialize(self):
        expected = dict(version=matrix.SURVEY_VERSION, contractSha256=io.sha(self.bound.execution_raw),
            surveyPolicySha256=io.sha(self.policy_raw), slots=list(self._slots[self.first-1:]))
        path = self.storage/'campaign.json'
        try:
            if not matrix.present(path):
                require({p.name for p in self.storage.iterdir()} == {'lock'}, 'orphan survey ledger')
                io.exclusive(path, io.encoded(expected))
            require(matrix.json_equal(io.read_owned(path), expected), 'survey campaign drift cannot reset consumption')
        except Exception as exc:
            self.abort(None, 'stored-survey-campaign-rejected', type(exc).__name__)
            raise

    def abort(self, ordinal, reason, error_type):
        """共有資源や台帳不整合は従来どおり全体停止する。"""
        matrix.MatrixLedger.stop(self, ordinal, reason, error_type)

    def path(self, stage, ordinal):
        if stage in {'failure', 'rejection'}:
            self.slot(ordinal)
            return self.storage/f'{stage}-{ordinal:04d}.json'
        return super().path(stage, ordinal)

    def stop(self, ordinal, reason, error_type):
        """取得器による局所拒否を保存する。失敗の確定は別の明示操作で行う。"""
        if reason not in LOCAL_REJECTIONS or type(ordinal) is not int or not self.first <= ordinal <= 92:
            self.abort(ordinal, reason, error_type)
            return
        value = dict(self.slot(ordinal), reason=reason, errorType=error_type)
        self.rejection_valid(value, ordinal)
        path = self.path('rejection', ordinal)
        if not matrix.present(path):io.exclusive(path, io.encoded(value))
        else:self.rejection_valid(io.read_owned(path), ordinal)

    def rejection_valid(self, value, ordinal):
        self.identity(value, ordinal, {'reason', 'errorType'})
        require(value['reason'] in LOCAL_REJECTIONS and isinstance(value['errorType'], str)
            and re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', value['errorType']) is not None, 'survey local rejection')

    def failure_valid(self, value, ordinal):
        self.identity(value, ordinal, {'status', 'phase', 'rejectionSha256', 'observation', 'eligibleForMeasurement'})
        require(value['status'] == 'evaluation_failed' and value['phase'] in FAILURE_PHASES
            and value['eligibleForMeasurement'] is False, 'survey failure is not a measurement')
        self.rejection_valid(self.read('rejection', ordinal), ordinal)
        require(value['rejectionSha256'] == io.sha(io.read_regular(self.path('rejection', ordinal))),
            'survey failure rejection drift')
        control = Path('.venv/production-matrix-launch-controls')/self.bound.contract['campaignId']
        raw = self.reference(value['observation'], expected_path=control/f'failure-observation-{ordinal:04d}.json')
        observation = matrix.strict_json(raw)
        require(isinstance(observation, dict) and set(observation) == {'version', 'slot', 'phase',
            'resourceProof', 'stageReceipt', 'primary', 'independent', 'parent'} and observation['version'] == VERSION
            and matrix.json_equal(observation['slot'], self.slot(ordinal))
            and observation['phase'] == value['phase'], 'survey failure observation identity')
        proof = matrix.strict_json(self.reference(observation['resourceProof'], expected_path=control/'survey-resource-proof.json'))
        require(proof.get('sourceCommit') == self.bound.contract['sourceCommit']
            and proof.get('executionSha256') == io.sha(self.bound.execution_raw)
            and proof.get('status') == 'matrix_deployment_resources_verified_launch_not_enabled',
            'survey failure current resources required')
        phase = value['phase']
        receipt_root = Path(self.bound.contract['outputRelativeRoot'] + ('' if phase == 'primary' else '-independent'))/f'attempt-{ordinal:04d}'
        receipt_name = 'receipt.json' if phase == 'primary' else 'independent-receipt.json'
        receipt = matrix.strict_json(self.reference(observation['stageReceipt'], expected_path=receipt_root/receipt_name))
        require(matrix.json_equal(receipt.get('slot'), self.slot(ordinal)), 'survey failed stage receipt identity')
        if phase == 'primary':
            require(matrix.present(self.path('started', ordinal)) and type(receipt.get('primaryModelTrajectories')) is int
                and receipt['primaryModelTrajectories'] == 1
                and type(receipt.get('namespaceExitCode')) is int, 'survey primary invocation ended')
        else:
            require(matrix.present(self.path('independent', ordinal))
                and type(receipt.get('independentInvocations')) is int and receipt['independentInvocations'] == 1
                and type(receipt.get('exitCode')) is int, 'survey independent invocation ended')
        hashes = receipt.get('artifactSha256')
        require(isinstance(hashes, dict) and len(hashes) <= 1024, 'survey failed receipt inventory')
        if phase == 'primary':
            import production_canary_evidence as evidence
            from production_matrix_evidence import PROVIDER_ARTIFACTS
            for name in hashes:
                if name not in PROVIDER_ARTIFACTS:evidence.artifact_name(name)
        else:
            import production_matrix_score as score
            require(set(hashes) <= score.ARTIFACTS, 'survey failed independent artifact names')
        for name, digest in hashes.items():
            require(io.sha(io.read_regular(self.repository/receipt_root/name)) == io.pin(digest),
                'survey failed stage original drift')
        rejection = self.read('rejection', ordinal)['reason']
        require(rejection in ({'primary-capture-rejected'} if phase == 'primary' else
            {'independent-capture-failed'} if phase == 'independent' else
            {'parent-original-verification-failed', 'independent-safety-or-integrity-unresolved'}),
            'survey failure phase and rejection mismatch')
        require(not matrix.present(self.path('review', ordinal)), 'survey failed slot cannot also be measured')
        if phase == 'primary':
            require(not matrix.present(self.path('primary', ordinal))
                and isinstance(observation['primary'], dict)
                and observation['primary'].get('status') == 'primary_capture_stopped'
                and type(observation['primary'].get('actualNamespaceInvocations')) is int
                and observation['primary']['actualNamespaceInvocations'] == 1
                and observation['independent'] is None and observation['parent'] is None,
                'survey failed primary observation')
        elif phase == 'independent':
            require(matrix.present(self.path('primary', ordinal)) and isinstance(observation['independent'], dict)
                and observation['independent'].get('status') == 'matrix_independent_capture_stopped'
                and observation['parent'] is None, 'survey failed independent observation')
        else:
            require(matrix.present(self.path('independent', ordinal)) and isinstance(observation['parent'], dict)
                and observation['parent'].get('ledgerFinalized') is not True,
                'survey failed parent observation')

    def _checked_last(self, *, allow_stopped=False):
        require(allow_stopped or not matrix.present(self.storage/'stop.json'), 'survey globally stopped')
        ordinal = None
        try:
            files = {p.name for p in self.storage.iterdir()}
            stages = matrix.STAGES + ('failure', 'rejection')
            allowed = {'lock', 'campaign.json'} | ({'stop.json'} if allow_stopped else set())
            allowed |= {f'{stage}-{n:04d}.json' for stage in stages for n in range(self.first, 93)}
            require(files <= allowed, 'unknown survey ledger record')
            count = sum(n.startswith('attempt-') for n in files)
            last = self.first+count-1
            require({f'attempt-{n:04d}.json' for n in range(self.first, last+1)} <= files, 'survey reservation gap')
            for ordinal in range(self.first, 93):
                if ordinal > last:
                    require(not any(matrix.present(self.path(s, ordinal)) for s in stages[1:]), 'unreserved survey stage')
                    continue
                require(matrix.json_equal(self.read('attempt', ordinal), self.slot(ordinal)), 'survey attempt drift')
                previous = True
                for stage in matrix.STAGES[1:]:
                    submitted = matrix.present(self.path(stage, ordinal))
                    require(not submitted or previous, 'survey stage gap')
                    if submitted:
                        value = self.read(stage, ordinal)
                        if stage == 'started':require(matrix.json_equal(value, self.slot(ordinal)), 'survey start drift')
                        elif stage == 'primary':self.primary_valid(value, ordinal)
                        elif stage == 'independent':self.independent_valid(value, ordinal)
                        else:self.review_valid(value, ordinal)
                    previous = submitted
                if matrix.present(self.path('rejection', ordinal)):
                    self.rejection_valid(self.read('rejection', ordinal), ordinal)
                    require(not matrix.present(self.path('review', ordinal)), 'survey rejected slot cannot be measured')
                if matrix.present(self.path('failure', ordinal)):
                    self.failure_valid(self.read('failure', ordinal), ordinal)
                require(ordinal == last or self.terminal(ordinal), 'survey unfinished preceding slot')
            return last
        except Exception as exc:
            self.abort(ordinal, 'stored-survey-evidence-rejected', type(exc).__name__)
            raise

    def checked_count(self):
        return self._checked_last()

    def terminal(self, ordinal):
        return matrix.present(self.path('review', ordinal)) or matrix.present(self.path('failure', ordinal))

    def latest_pending(self, ordinal):
        super().latest_pending(ordinal)
        require(ordinal >= self.first and not matrix.present(self.path('failure', ordinal)), 'survey slot already failed')

    def reserve(self, ordinal):
        with self.locked():
            self.initialize()
            last = self.checked_count()
            require(type(ordinal) is int and ordinal == last+1 and ordinal <= 92, 'survey fixed order or limit')
            require(last < self.first or self.terminal(last), 'survey previous result pending')
            value = self.slot(ordinal)
            io.exclusive(self.path('attempt', ordinal), io.encoded(value))
            return value

    def record_failure(self, ordinal, phase, observation):
        """親が現物検査を再実施して作った観測だけを終端失敗として保存する。"""
        with self.locked():
            self.initialize();self.latest_pending(ordinal)
            try:
                value = dict(self.slot(ordinal), status='evaluation_failed', phase=phase,
                    rejectionSha256=io.sha(io.read_regular(self.path('rejection', ordinal))),
                    observation=observation, eligibleForMeasurement=False)
                self.failure_valid(value, ordinal)
            except Exception as exc:
                self.abort(ordinal, 'submitted-survey-failure-rejected', type(exc).__name__)
                raise
            io.exclusive(self.path('failure', ordinal), io.encoded(value))

    def summary(self):
        with self.locked():
            self.initialize();stopped = matrix.present(self.storage/'stop.json')
            last = self._checked_last(allow_stopped=stopped)
            counts = {s:0 for s in matrix.STAGES+('failure',)}
            correct = incorrect = 0
            for n in range(self.first, last+1):
                for stage in counts:counts[stage] += matrix.present(self.path(stage, n))
                if matrix.present(self.path('review', n)):
                    correct += self.read('review', n)['accuracy'] is True
                    incorrect += self.read('review', n)['accuracy'] is False
            old = self.policy['priorSlots']
            correct += sum(x['status'] == 'measured_correct' for x in old)
            incorrect += sum(x['status'] == 'measured_incorrect' for x in old)
            failed = counts['failure']+sum(x['status'] == 'evaluation_failed' for x in old)
            complete = correct+incorrect+failed
            return dict(status='stopped' if stopped else 'complete' if complete == 92 else 'in_progress',
                maximumPrimary=92, primaryReserved=len(old)+counts['attempt'],
                primaryLaunchMarked=sum((x.get('primary') or {}).get('actualNamespaceInvocations') == 1 for x in self.prior)+counts['started'],
                primaryCompleted=sum((x.get('primary') or {}).get('status') == 'primary_capture_awaits_independent_review' for x in self.prior)+counts['primary'],
                independentReserved=sum((x.get('independent') or {}).get('independentInvocations') == 1 for x in self.prior)+counts['independent'],
                parentVerified=correct+incorrect, measuredCorrect=correct, measuredIncorrect=incorrect,
                evaluationFailed=failed, evaluatedSlots=complete, unattemptedSlots=92-len(old)-counts['attempt'],
                pendingSlots=len(old)+counts['attempt']-complete, missingMeasurements=92-correct-incorrect,
                carriedSlots=len(old), certifiesSkillGate=False, certifiesRelease=False)
