"""Prepare only own metadata activation after actual frozen main full acceptance."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import re
import subprocess
import yaml

t = Path(__file__).resolve().parent
w = t / 'ops013-reservation'
base = '15feb3d74aa8b0465b2c7a02d25c03d5dcade7a6'
old_source = '5e0fc4f36a4c0abe44efe084dd88c002a5d7d6da'
old_branch = 'chore/OPS-014-gz021-metadata-freeze'
branch = 'chore/OPS-014-frozen-416-contract-repair'
acceptance_path = t / 'ops014-gz021-freeze-15feb3d-full-main-independent-review.json'
acceptance_raw = acceptance_path.read_bytes()
accepted = json.loads(acceptance_raw)
assert accepted['mustFix'] == [] and accepted['actualFrozenMain'] == base
assert accepted['actualFrozenMainAccepted'] and accepted['fullMainCiAccepted']
assert accepted['mainCiNumber'] == 847 and accepted['actualTestsPassed'] == 742 and accepted['testSkipped'] == 0
assert accepted['actor'] == '/root/gz022_planning_independent_review'
assert accepted['activationMetadataPreparationMayProceed'] is True
candidate_path = t / 'ops014-frozen-416-activation-uncommitted-candidate.json'
assert not candidate_path.exists()
git = lambda *a: subprocess.check_output(['git', '-c', 'core.longpaths=true', '-c', 'core.autocrlf=false', '-C', str(w), *a])
dec = lambda *a: git(*a).decode().strip()
assert dec('rev-parse', 'HEAD') == old_source and dec('branch', '--show-current') == old_branch
assert dec('rev-parse', 'main') == base and not git('status', '--porcelain=v1', '--untracked-files=all')
assert dec('ls-remote', 'origin', 'refs/heads/main') == base + '\trefs/heads/main'
assert not dec('ls-remote', 'origin', 'refs/heads/' + branch)
exists = subprocess.run(['git', '-C', str(w), 'show-ref', '--verify', '--quiet', 'refs/heads/' + branch])
assert exists.returncode == 1
before_plan = yaml.safe_load(git('show', base + ':specs/coordination/program-plan.yaml', '--'))
before_active = yaml.safe_load(git('show', base + ':specs/coordination/active-work.yaml', '--'))
event = before_plan['recovery']
assert before_plan['status'] == 'frozen' and event['taskId'] == 'OPS-014'
assert event['sourceCommit'] == '36b986a65e23671d0b08134d1c4163833a59fbd7' and event['affectedTasks'] == ['GZ-021']
assert event['verificationPath'] == 'evidence/OPS-014/recovery-proof.json'
own = next(x for x in before_active['tasks'] if x['taskId'] == 'OPS-014')
foundation = next(x for x in before_plan['foundationTasks'] if x['taskId'] == 'OPS-014')
assert own['status'] == foundation['status'] == 'reserved' and own['agentRole'] == 'coordinator'
assert foundation['completionRef'] == 'ISSUE-142' and foundation['mergeCommit'] is None
assert own['branch'] == old_branch and own['issue'] == 142 and own['moduleIds'] == ['MOD-GOV']
assert len(before_active['tasks']) == 3 and sum(x['riskLevel'] in ['high', 'critical'] for x in before_active['tasks']) == 1
assert own['lease'] == {'acquiredAt': '2026-10-24T21:42:30Z', 'expiresAt': '2026-10-31T21:42:30Z'}
now = datetime.now(timezone.utc)
assert now < datetime.fromisoformat(own['lease']['expiresAt'].replace('Z', '+00:00'))
intent_raw = git('show', base + ':evidence/OPS-013/contract-repair-authorization.json', '--')
assert hashlib.sha256(intent_raw).hexdigest() == '4f344a74a47a56ff1c3b0e27c368767e0cb779ebc61e721b263f102b39a83401'
intent = json.loads(intent_raw)
claims = [x['path'] for x in intent['successor']['paths']]
assert own['exclusivePaths'] == claims and own['sharedPaths'] == []
for item in intent['successor']['paths']:
    raw = git('show', base + ':' + item['path'], '--')
    assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['gitBlobSha256']
assert dec('rev-parse', base + '^{tree}') == dec('rev-parse', old_source + '^{tree}')
subprocess.run(['git', '-c', 'core.longpaths=true', '-C', str(w), 'switch', '--create', branch, 'main'], check=True)
assert dec('rev-parse', 'HEAD') == base and not git('status', '--porcelain=v1', '--untracked-files=all')

program = w / 'specs/coordination/program-plan.yaml'
s = program.read_text('utf-8');start = s.index('  - taskId: OPS-014\n');end = s.index('\nwaves:\n', start)
block = s[start:end]
assert block.count('    status: reserved\n') == 1
program.write_text(s[:start] + block.replace('    status: reserved\n', '    status: in_progress\n', 1) + s[end:], encoding='utf-8', newline='\n')
expected_plan = copy.deepcopy(before_plan)
next(x for x in expected_plan['foundationTasks'] if x['taskId'] == 'OPS-014')['status'] = 'in_progress'
assert yaml.safe_load(program.read_bytes()) == expected_plan
active = w / 'specs/coordination/active-work.yaml'
s = active.read_text('utf-8');marker = '- taskId: OPS-014\n';assert s.count(marker) == 1
prefix, tail = s.split(marker)
for left, right in [('status: reserved\n', 'status: in_progress\n'), ('agentRole: coordinator\n', 'agentRole: implementer\n'), ('branch: ' + old_branch + '\n', 'branch: ' + branch + '\n'), ('baseSha: ' + own['baseSha'] + '\n', 'baseSha: ' + base + '\n')]:
    assert tail.count(left) == 1
    tail = tail.replace(left, right, 1)
active.write_text(prefix + marker + tail, encoding='utf-8', newline='\n')
expected_active = copy.deepcopy(before_active)
next(x for x in expected_active['tasks'] if x['taskId'] == 'OPS-014').update(status='in_progress', agentRole='implementer', branch=branch, baseSha=base)
assert yaml.safe_load(active.read_bytes()) == expected_active

task_path = w / 'specs/tasks/OPS-014.md'
old_task = task_path.read_text('utf-8')
front = yaml.safe_load(old_task.split('---', 2)[1])
old_commands = re.findall(r'```bash\n(.*?)\n```', old_task, re.S)
assert len(old_commands) == 1
static_commands = old_commands[0].replace(own['baseSha'], base).replace(old_branch, branch).splitlines()
assert len(static_commands) == 15
extra = ['python specs/poc/check_program.py --repo-root .', 'python specs/poc/test_program.py', 'python -m pytest tests/governance -q --junitxml=evidence/OPS-014/recovery-validation/governance.xml']
verify_at = next(i for i, line in enumerate(static_commands) if line.startswith('make verify '))
code_commands = static_commands[:verify_at] + extra + static_commands[verify_at:]
archive_commands = [line for line in static_commands if not line.startswith('make verify ')]
archive_commands.insert(-1, extra[0])
assert len(code_commands) == 18 and len(archive_commands) == 15
front.update(status='in_progress', agentRole='implementer', baseSha=base, workBranch=branch)
claim_lines = ''.join('- `' + path + '`\n' for path in claims)
context = 'Task: OPS-014\nIssue: #142\nBranch: ' + branch + '\nBase: ' + base + '\nSource/tree/execution: UNCOMMITTED metadata activation proposal; contract code untouched\n'
roles = 'Owner ElectricDogCN; Coordinator program-coordinator-agent; Implementer poc-contract-repair-implementation-agent (/root); Reviewer independent-review-agent (/root/gz022_planning_independent_review); Integrator integration-agent.'
sections = {
    '背景与目标': '真实授权416返回33字节诊断正文，与GZ-021的metadata profiling空正文要求冲突。原始登记main36b与独立冻结main15f均已完整接受。本阶段先独立metadata activation提交，再仅修复原始授权的两文件；本候选未写合同代码或运行新实验。',
    '输入与输出': '输入：实际接受的冻结main15f、原OPS-013不可变授权、原33字节响应、原决定及独立评估。输出：真实修复C的两文件与新回归、五项严格绑定F/C的原始验证和另行POC专项，随后Own Evidence归档A。保留GZ-021完成身份及完整六字段冻结事件。',
    '允许范围': '- `specs/coordination/program-plan.yaml`（仅自身Foundation状态）\n- `specs/coordination/active-work.yaml`（仅自身当前上下文）\n- `specs/tasks/OPS-014.md`\n- `evidence/OPS-014/**`\n\n独立metadata激活提交成立后的代码仅：\n\n' + claim_lines + '\n验证C之后、解冻基线之前仅允许Own Evidence归档，不能再改Task/Active/Program或代码。',
    '禁止范围': '- 不改原OPS-013授权及原始失败/33字节原件、模块所有权、foreign任务/租约、普通账本、政策、工作流、Schema、样本/资源/质量/时间阈值及原13项测量。\n- 不删除或放宽原test198及断言，不改变其他Range disposition、storage或auth语义。\n- 不在冻结期间推进普通POC、重用旧实验批准、修改系统时间或将旧10k失败改标通过。',
    '依赖与集成顺序': '- 已满足实际完成OPS-013、独立原始登记及实际冻结main15f完整接受。顺序：metadata激活单独提交 → 两文件修复及真实验证C → 仅Own Evidence归档A作为同一代码PR头 → A最新完整CI及独立审查 → 正常合入R并验收其自己的主线CI → 另提metadata-only解冻 → 正常Review/Completion。普通POC只在实际解冻后的新源和批准窗口继续。',
    '独占写范围': claim_lines,
    '共享修改范围': '- 无。',
    '协作与交接': context + '\n- ' + roles + '\n- 原租约2026-10-24T21:42:30Z→2026-10-31T21:42:30Z保持，不续期；MOD-GOV/high/FOUNDATION/order10及原依赖、两claims、三活动一high保持。',
    '验收标准': '- [x] 原始独立预留及实际main接受，真实独立冻结main15f完整接受；原授权和两旧Git字节保持。\n- [ ] 激活metadata独立先于合同代码，状态in_progress/implementer和实际分支/基线一致。\n- [ ] 仅supported/unsatisfiable允许空或有界非空正文；保留65536上限及请求/416/Content-Range/source/object/version/UTC/hash/长度。\n- [ ] 原test198字节与断言保持；local-v1及production覆盖真实33字节、其他诊断、65536接受/65537拒绝及各绑定反例，其他disposition/storage/auth保持。\n- [ ] 真正固定C完成直接五项严格证明、非空零失败/错误/跳过JUnit、独立POC专项；归档A仅Own Evidence，最新同头CI及实际R自己的CI接受。\n- [ ] 证明在独立解冻基线中已经存在；独立解冻及实际main接受后正常Review/Completion，最后代码身份绑定实际代码PR/R。',
    '必须执行的测试': '### 固定修复源C\n\n```bash\n' + '\n'.join(code_commands) + '\n```\n\n以上18项在修复源固定后执行。运行记录先解析HEAD为实际40位C，生命周期、协调及verify使用完整C/F和本分支；原始日志保留真实Source Commit/Command/Exit Code。direct governance的JUnit路径属于Own Evidence；verify另留真实完整日志和对应结果，不能互相替代。另在Windows以同一C运行原test198及新增诊断正反例，完整POC专项在native环境实际执行。测试中的请求/身份/UTC是合成夹具，真实33字节只复用字节内容，不冒称新10k实验。\n\n### C之后仅Own Evidence归档A\n\n```bash\n' + '\n'.join(archive_commands) + '\n```\n\n本段仅用于C已真正通过上一阶段且A只追加Own Evidence的情形：A执行自己的15项静态/范围检查及最新同头完整hosted CI，不把C结果冒称A重新执行。C→A→实际R的所有后续提交只能Own Evidence；不得改Task/Active/Program/代码。R真实合入且其自己的主线检查/完整CI/独审接受后，才可由独立thaw消费C证明。证明不是归档时就已合入或解冻获准。后续thaw/Review/Completion在各自允许元数据阶段更新自身上下文和准确阶段命令，履行各自直接检查、最新完整hosted CI及实际main接受；没有追溯豁免本阶段已声明的18/15项。',
    '风险': '把未接受基线当冻结、在单一提交中先代码后激活、改变原断言或预算、伪造执行或将归档A当已合入。以原授权/两旧Git字节、分离metadata历史、固定源原件及独立审查控制。C之后的控制元数据变动会使证明失效，不能隐瞒恢复或重用旧日志。',
    '回滚': '未合入可撤回本实现提案并保留全部原始失败和运行材料，实际冻结main继续保留。冻结owner不得在独立解冻前完成/释放。若已合入代码需要修正或回退，按同一合法冻结事件在登记范围内另验证真实新源；不以手工改状态或旧结果冒充恢复，解冻仍须单独metadata-only交易。',
    'Evidence': 'freeze-main-accepted-independent-review.json绑定实际F及CI847；原decision、原授权引用及33字节失败原件保持。当前仅metadata activation提案，代码和当前18/15项尚未执行；recovery-proof.json不建占位PASS，只有真实验证完成后才按精确六字段proof与五命令结构归档。POC专项单独归档，不给严格proof.commands添加额外键。',
}
task = '---\n' + yaml.safe_dump(front, sort_keys=False, allow_unicode=True, width=10000) + '---\n\n# OPS-014 frozen metadata 416 repair\n\n'
for heading, body in sections.items():
    task += '## ' + heading + '\n\n' + body.strip() + '\n\n'
task_path.write_text(task, encoding='utf-8', newline='\n')
e = w / 'evidence/OPS-014'
with (e / 'freeze-main-accepted-independent-review.json').open('xb') as stream:
    stream.write(acceptance_raw)
facts = dict(kind='metadata_activation_proposal_before_contract_code', preparedAt=now.isoformat(), taskId='OPS-014', issue=142,
    base=base, branch=branch, frozenRecovery=event, originalLease=own['lease'], exactClaims=claims,
    authoritySha256=hashlib.sha256(intent_raw).hexdigest(), acceptedFrozenMainReviewSha256=hashlib.sha256(acceptance_raw).hexdigest(),
    originalContractBlobs=intent['successor']['paths'], codePhaseCommands=18, evidenceOnlyArchiveCommands=15,
    metadataOnly=True, codeWritten=False, validationExecuted=False, experimentApproved=False, qualificationAccepted=False)
with (e / 'activation-proposal.json').open('x', encoding='utf-8', newline='\n') as stream:
    stream.write(json.dumps(facts, ensure_ascii=False, indent=2) + '\n')
summary = '# OPS-014 frozen repair activation proposal\n\n' + context + '\nActual F/main15f fully accepted; this candidate changes only Own metadata to prepare implementer execution. Code remains the original approved two Git blobs; current code/proof/experiments remain unexecuted and unqualified. CodeC18 and later Evidence-onlyA15 are separately declared prospectively in Task.\n'
(e / 'summary.md').write_text(summary, encoding='utf-8', newline='\n')
(e / 'handoff.md').write_text(summary + '\n' + roles + '\n\nActual files: changed-files.md; exact code scope and all forbiddens: scope.md and Task. Commands: commands.txt, planned only. Original lease/claims/order unchanged. Next Reviewer: exact activation metadata and prospective phase boundary before commit. Next Implementer: commit metadata activation independently before any test/checker change; retain original test198 and real33 baseline, run actual red regression, then narrowly repair and validate fixedC. AfterC only OwnEvidenceA; same codePR headA/actualR/latestCI, separate thaw. Rollback: rollback.md; no frozen-owner release or false PASS.\n', encoding='utf-8', newline='\n')
(e / 'commands.txt').write_text(context + '\nCODE C18 planned, HEAD resolved to actual fixed source at execution:\n' + '\n'.join(code_commands) + '\n\nEVIDENCE-ONLY A15 planned, conditional on real prior C acceptance:\n' + '\n'.join(archive_commands) + '\n', encoding='utf-8', newline='\n')
(e / 'scope.md').write_text('# OPS-014 current scope\n\nOnly Own Program/Active/Task/Evidence in this metadata activation proposal. After its separate commit, only these two source paths under the original immutable authorization:\n\n' + claim_lines + '\nKeep all original response/source/version/window/hash/count bounds, 65536 cap, original13, oldtest198, other dispositions/storage/auth. After validatedC until thaw base, only Own Evidence may change. No ordinary POC work during Program freeze.\n', encoding='utf-8', newline='\n')
(e / 'rollback.md').write_text('# Rollback\n\n' + sections['回滚'] + '\n', encoding='utf-8', newline='\n')
(e / 'follow-ups.md').write_text('# Remaining work\n\n' + sections['依赖与集成顺序'] + '\n\nDo not clean the active freeze branch or amend foreign leases. Source validation and actual repair/main/thaw/normal completion remain required; no qualification transferred from old10k.\n', encoding='utf-8', newline='\n')
(e / 'test-results/README.md').write_text('# OPS-014 validation stages\n\nF prerequisites have their own accepted main847 proof. This activation candidate has no new code validation. Task declares codeC18 including exact five mandatory proof commands and separate actual POC selftests; after C only EvidenceA15+new-headCI, then actual R own mainCI. Prior local/CI results do not count as execution on a new source. No recovery-proof placeholder is created.\n', encoding='utf-8', newline='\n')
assert not (e / 'recovery-proof.json').exists()
paths = sorted(set(dec('diff', '--name-only', base, '--').splitlines() + dec('ls-files', '--others', '--exclude-standard').splitlines() + ['evidence/OPS-014/changed-files.md']))
metadata = {'specs/coordination/program-plan.yaml', 'specs/coordination/active-work.yaml', 'specs/tasks/OPS-014.md'}
assert metadata <= set(paths) and all(p in metadata or p.startswith('evidence/OPS-014/') for p in paths)
(e / 'changed-files.md').write_text('# OPS-014 metadata activation inventory\n\nBase: ' + base + '\n\n' + ''.join('- `' + p + '`\n' for p in paths), encoding='utf-8', newline='\n')
subprocess.run(['git', '-c', 'core.longpaths=true', '-C', str(w), 'diff', '--check', base], check=True)
for path in claims:
    assert (w / path).read_bytes() == git('show', base + ':' + path, '--')
snapshot = [dict(path=p, bytes=(w / p).stat().st_size, sha256=hashlib.sha256((w / p).read_bytes()).hexdigest()) for p in paths]
with candidate_path.open('x', encoding='utf-8', newline='\n') as stream:
    stream.write(json.dumps(dict(facts, changedPaths=paths, fileSnapshot=snapshot, authorHead=dec('rev-parse', 'HEAD'), preparedOnly=True), ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(branch=branch, base=base, changedPaths=len(paths), preparedOnly=True, codeWritten=False), ensure_ascii=False), flush=True)
