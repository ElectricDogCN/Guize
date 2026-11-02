"""Prepare source-labelled reporting from existing qualified runs; execute no experiment."""
from pathlib import Path
import datetime as dt
import hashlib
import json

ROOT = Path(__file__).resolve().parent
AUTHOR = ROOT / 'poc005-thaw-integration'
EVIDENCE = AUTHOR / 'evidence/POC-005'
ANALYSIS = ROOT / 'poc005-source-bound-scale-analysis-v1/analysis.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def ref(path, label=None):
    return f'[{label or path}]({path})'


def main():
    report = EVIDENCE / 'local-v1-scale-exit-report.md'
    disk_path = EVIDENCE / 'local-v1-retained-database-snapshot.json'
    assert not report.exists() and not disk_path.exists(), 'exclusive new report outputs'
    analysis = load(ANALYSIS)
    assert analysis['sourceContextUnchanged'] and not analysis['experimentExecuted']
    q = load(ROOT / 'poc005-attempt010-full-validation-independent-assessment.json')
    assert q['scale1mAccepted'] and q['completeFrozenValidateExecutionAccepted'] and not q['mustFix']
    ix = load(EVIDENCE / 'qualified-local-1m-attempt010-v1/index.json')
    assert ix['retainedItems'] == len(ix['files']) == 45
    retained = {x['sourceRef']: x['retainedRef'].removeprefix('evidence/POC-005/') for x in ix['files']}
    audit_ref = retained['poc005-attempt010-full-validation-independent-assessment.json']
    analysis_ref = retained['poc005-source-bound-scale-analysis-v1/analysis.json']
    cleanup_ref = retained['poc005-attempt010-cleanup-and-evidence-integration-result-independent-review.json']
    actual_runtime = ROOT / 'poc005-attempt010-runtime-ed8fbf3'
    dbs = []
    for p in sorted((actual_runtime / 'evidence/POC-005/profiles/local-v1/v1/attempt-010').rglob('*.sqlite')):
        s = p.stat()
        dbs.append({'runtimeRelativePath': p.relative_to(actual_runtime).as_posix(), 'logicalBytes': s.st_size, 'mtimeNs': s.st_mtime_ns})
    assert len(dbs) == 10
    disk = {'kind': 'POST_EXECUTION_RETAINED_DATABASE_LOGICAL_SIZE_SNAPSHOT',
            'observedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
            'runtime': q['source'], 'attempt': 'attempt-010', 'files': dbs,
            'totalLogicalBytes': sum(x['logicalBytes'] for x in dbs),
            'databaseOpenedOrChanged': False, 'physicalAllocatedBytesMeasured': False,
            'experimentExecuted': False}
    disk_path.write_text(json.dumps(disk, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = analysis['rows']
    lines = [
        '# POC-005 local-v1 规模、来源成本与退出报告', '',
        '**报告状态：提交独立退出审查。** 三次本地执行资格各自成立；本报告建议以 attempt-010 作为唯一正式 local-v1 主执行，008/009 为保留原源码归属的规模支持。正式结果、profile 完整校验、最终源/CI 与主线验收仍待本次后续步骤。', '',
        '## 原始执行与适用范围', '',
        '| 执行 | 文件 / 目录 | 受测提交 | 输入 → 输出 | 原资格上下文 |',
        '| --- | --- | --- | --- | --- |',
    ]
    contexts = ['71b77776a9080091ee3b10042e66f5c9dcff41a4', 'da1e85ab152e6d1f7e101254c4119375c8412557', '77d99effc1a0e1524dcf1795d1c0aff359ab219c']
    representations = ['plain JSONL → plain JSONL', 'gzip → plain JSONL', 'gzip → gzip']
    archive_dirs = ['qualified-local-10k-attempt008-v1', 'qualified-local-100k-attempt009-v1', 'qualified-local-1m-attempt010-v1']
    for row, context, representation, archive in zip(rows, contexts, representations, archive_dirs):
        m = {x['id']: x['actual'] for x in row['measurements']}
        lines.append(f"| {row['attempt']:03} | {m['file_count']} / {m['directory_count']} | `{row['testedSource']['commit']}` | {representation} | `{context}`；{ref(archive+'/index.json','资格原件索引')} |")
    lines += ['', '三次使用固定 500 目录、最大深度 12 的受控层次；源码、表示方式、来源缓存及运行时条件存在差异，不能把时间变化全归因于规模。逻辑素材总字节分别为 17,920,000 / 179,200,000 / 1,792,000,000 B，平均 1792 B；不等于文件逐个同尺寸、实际磁盘分配量或 700TB 传输。', '',
              '## 原 13 项观测', '', '| 项目 | 单位 | 008 / 10k | 009 / 100k | 010 / 1m |', '| --- | --- | --- | --- | --- |']
    units = ['files','directories','levels','bytes','requests/min','changes/hour','objects/s','s','MiB','boolean','boolean','boolean','boolean']
    for i, measurement in enumerate(rows[0]['measurements']):
        key = measurement['id']
        values = [{v['id']: v['actual'] for v in row['measurements']}[key] for row in rows]
        lines.append('| ' + ' | '.join([key, units[i]] + [str(v).lower() for v in values]) + ' |')
    lines += ['', '枚举速率含目录对象；增量耗时仅为受控三变更已送达之后的 scanner 阶段。内存为该 scanner 原生全生命周期 PeakWorkingSet，未做基线相减，不是控制器、提供方、验证器或宿主机总内存。三变更除以实际观测窗口得到归一化速率，不是自然生产变化率。', '',
              '## 来源遍历与端到端成本', '', '| 执行 | 每遍页数 / 对象 | 第一遍墙钟跨度 / 可见请求耗时和(s) | 第二遍墙钟跨度 / 可见请求耗时和(s) | scanner 枚举(s) | 三变更观察窗口(s) |', '| --- | --- | --- | --- | --- | --- |']
    for row in rows:
        runs = list(row['sourceNormalListingRuns'].values())
        a,b = runs
        assert a['pages'] == b['pages'] and a['objects'] == b['objects']
        lines.append(f"| {row['attempt']:03} | {a['pages']} / {a['objects']} | {a['normalTraversalWallSpanSeconds']} / {a['sumVisibleNormalRequestSeconds']} | {b['normalTraversalWallSpanSeconds']} / {b['sumVisibleNormalRequestSeconds']} | {row['nativeScannerEnumerationSeconds']} | {row['controlledChangeObservationSeconds']} |")
    lines += ['', '两个完整来源遍历不能被 scanner 速率代表。010 的两次遍历各约 13 分钟，均在 scanner 枚举前完成；1m 枚举约 8分56秒，完整原执行约37分21秒。上表可见请求耗时和与跨度含义不同；未计入的准备、探针、故障、三次物理变更、后处理和审查不可当成零成本。原始 UTC 起止、页描述、完整分布及物理摘要见 '+ref(analysis_ref,'按源版本分析原件')+'。', '',
              '010 真实四种故障为受控适配器 429、503、断连及过期授权，分别实际尝试 2/2/2/1 次；授权过期不重试。策略最多一次重试、遵守有界 Retry-After、最大退避0.25s。适配器配额6000请求/60s，固定单调时钟桶从网关启动计；原生 OpenList 和生产提供方实际配额未知。故障注入不证明自然发生率。详见 '+ref('profiles/local-v1/v1/attempt-010/windows-adapter-quota.json','原额度说明')+'及资格审查原件。', '',
              '## 目录、文件名与来源语义', '', '| 执行 | 目录直接孩子最大 / 平均 | 空目录 | 根直接孩子 / 文件 | ASCII / 非 ASCII 对象 |', '| --- | --- | --- | --- | --- |']
    for row in rows:
        f=row['fanout']; c=row['filenameDistributions']['characterSet']
        lines.append(f"| {row['attempt']:03} | {f['maximumDirectChildrenAmongRepresentedDirectories']} / {f['meanDirectChildrenAmongRepresentedDirectories']} | {f['directChildCountHistogram']['0']} | {f['unrepresentedNamespaceRootDirectChildren']} / {f['unrepresentedNamespaceRootDirectFiles']} | {c['ascii']} / {c['non_ascii']} |")
    lines += ['', '目录统计仅含500个有记录的目录；命名空间根单列。字符分类含文件与目录，扩展名分类仅文件。每组完整名字长度、路径深度、目录扇出直方图及扩展名数量保存在分析原件，原 filenameObjects、profiling 和 providerPages 的路径与哈希逐组保留，不据此宣称任意目录分布。', '']
    for row in rows:
        lines.append(f"- {row['attempt']:03} 扩展名分布：`{json.dumps(row['filenameDistributions']['extension'],ensure_ascii=False,sort_keys=True)}`；" + ref(row['filenameProfilingRef'].removeprefix('evidence/POC-005/'),'原 profiling')+'。')
    lines += ['', '五种原探针均完整保留：不变对象两次200/4096B且ETag相同；有界Range返回206/2B、`bytes 0-1/4096`；越界返回416/33B、`bytes */4096`；受控更新后200/4096B且ETag改变。010 ETag从`"6955b900-1000"`变为`"6955b902-1000"`。这只证明该来源配置的观测，不能当成强内容哈希、原生稳定对象ID或任意一致性保证；受控对象ID/版本映射仍是适配器身份。', '',
              '## 内存、临时盘与保留成本', '',
              f"010 scanner 峰值 32,632,832 B（31.12109375 MiB）。选定11224份原始材料物理总长578,041,112 B，最大单份44,022,011 B；这只对应选定交付范围，并非整个流程临时盘。运行时仍保留10个SQLite文件，当前逻辑总长 {disk['totalLogicalBytes']:,} B，详见 "+ref(disk_path.name,'只读长度快照')+'。未打开数据库、未测NTFS物理分配，尚不能给出整个宿主机峰值用盘。', '',
              '该3.17GB逻辑数据库包括scanner状态、映射及两份来源列表；固定输入、逻辑素材、选定原始材料、Git/bundle、旧失败与多份校验副本另占空间。后续部署预算必须分别预留并测量，不能用900MiB实验产物预算或31MiB scanner内存声称整个任务资源开销。现有冻结阈值没有改动。', '',
              '## 五项退出条件与本地建设决定', '',
              '| 原计划退出条件 | 已取得的本地证据 |', '| --- | --- |',
              '| 文件数、目录数/深度、平均大小、来源额度事实 | 三组原13项、固定层次与额度原件；1m主执行全量物理/类型校验 |',
              '| 确定性变化频率 | 各组三个真实create/update/delete及其原观测窗口、应用事件和后目录 |',
              '| 覆盖文件数、扇出/深度与变更率的规模模型 | 10k/100k/1m各自资格和完整直方图；范围为固定500目录受控层次 |',
              '| 枚举、增量、峰值内存实测 | 原生进程/wait/QPC/FILETIME与13项测量，来源HTTP成本另列 |',
              '| 文件名、提供方、Range和版本语义 | 完整filename/profile、两遍来源列表、五探针及原响应正文 |', '',
              '建议的本地退出决定是 pass，仅限现有 local-v1 测试域。010 的真实执行及完整冻结资格已由 '+ref(audit_ref,'独立资格审查')+'接受；008/009保持各自旧源资格。本报告不产生reviewer批准，正式结果须由独立审查者作出退出决定并记录真实批准时间，再运行完整profile命令。', '',
              '后续来源集成先固定源版本、分页/身份与扫描检查点，使用有界内存和磁盘状态；压缩用于实际物理交付预算。由于两遍完整来源遍历占主要成本，生产应先测真实人口、目录分布、自然更新、延迟和配额，再决定原生增量日志/change token、适应退避或分阶段索引。当前受控journal不能充当原生change token；这些替代方案尚未实现或获得性能资格。不能按1792B平均大小推算700TB文件数、扫描时长或费用。', '',
              '## 清理、漂移与历史', '',
              'scanner/controller原生wait均为0，完整冻结执行校验原session48531于2026-10-27T04:38:08.436310Z退出0。专用OpenList原PID35132于05:00:58–05:00:59Z按批准方法强制停止，实际等待完成/退出3221225786；这不是优雅或自然零退出。原connect_ex10035不足以证明端口关闭，后续实际原生TCP表和进程查询确认零监听/原进程不存在。详见 '+ref(cleanup_ref,'独立清理与证据集成接受')+'。', '',
              '三个受控叶子变化、固定素材、实例配置、10个运行数据库、4171条旧未跟踪路径和本地验证副本均保留，未声称还原。无运行实验残留；保留物因本次可复核证据义务暂不删除，不应作为常驻生产数据或联调实例。旧中断、007五项UTC资格失败、组件失败与更正均未改写；终态与资格来自后续各自实际执行。没有删除治理/Evidence历史。', '',
              '## 下一角色与正式检查', '',
              '独立审查本报告和三组资格后决定local-v1退出结果。正式index仅指向一个resultRef，result仅指向010 executionRef；原测试/批准时间不回填。结果进入真实Git兼容上下文后执行：', '',
              '```text', 'python specs/poc/check_program.py --profile local-v1 --require-results --poc POC-05', '```', '',
              '随后完成最终源Task检查、同头CI、独立源/结果审查、普通集成、实际主线验收及正常Review/Completion。正式本地退出不等于生产CAP-001/CAP-003、百度配额/接入、Ready、任务完成或完整V1完成。', '',
              '## 原始执行引用', '']
    for row in rows:
        relative=row['executionRef'].removeprefix('evidence/POC-005/')
        lines.append(f"- {ref(relative,format(row['attempt'],'03')+' execution')}；SHA256 `{row['executionSha256']}`；原测量/素材/资源/时序/wait均由该执行引用。")
    report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(report),'bytes':report.stat().st_size,'sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'retainedDbLogicalBytes':disk['totalLogicalBytes'],'originalArchiveItems':len(ix['files']),'experimentExecuted':False}))


if __name__ == '__main__':
    main()
