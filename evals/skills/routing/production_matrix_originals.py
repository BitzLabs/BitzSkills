"""公開行列のprovider原を完全inventory/NOFOLLOWで読取る。起動・予約・確定はしない。"""
from types import SimpleNamespace
import stat
import production_matrix_provider_evidence as provider

io=provider.io
trace=provider.trace
require=trace.require


def load_provider_capture(bound,ordinal,*,source_repository,artifact_repository,manifest_raw,schema_raw,context_raw):
    matrix=provider.evidence.matrix
    require(isinstance(bound,matrix.BoundExecution),'matrix fixed execution required')
    require(bound==matrix.bind(bound.execution_raw,bound.matrix.contract_raw,
        **dict(zip(matrix.inputs.INPUT_NAMES,bound.raw_inputs))),'matrix original reader fixed input drift')
    source_repository=provider.absolute_root(source_repository);artifact_repository=provider.absolute_root(artifact_repository)
    environment=provider.environment_spec(SimpleNamespace(bound=bound,ordinal=ordinal),source_repository,artifact_repository)
    base=artifact_repository/bound.contract['outputRelativeRoot']/f'attempt-{ordinal:04d}'
    io.safe_tree(base)
    receipt_raw=io.read_regular(base/'receipt.json');receipt=trace.strict_json(receipt_raw)
    require(isinstance(receipt,dict) and set(receipt)==provider.evidence.RECEIPT_KEYS
        and receipt['version']==provider.evidence.PROVIDER_VERSION,'matrix provider original receipt inventory')
    require(receipt['sourceCommit']==bound.contract['sourceCommit'] and trace.json_equal(receipt['slot'],bound.slot(ordinal))
        and receipt['cwd']==environment['cwd'],'matrix original reader source/slot/root drift')
    names=provider.evidence.inventory.artifact_inventory(base,receipt['artifactSha256'],
        additional_artifacts=provider.evidence.PROVIDER_ARTIFACTS)
    # 既知名のhardlinkも全集合のmetadataで拒否してから原内容を読む。
    for name in names:
        metadata=(base/name).lstat()
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink==1,'matrix original file type or hardlink')
    originals={name:io.read_regular(base/name) for name in names}
    context=provider.evidence.bind_originals(bound,ordinal,originals,receipt_raw,manifest_raw,schema_raw,context_raw)
    provider.verify_bytes(context,source_repository=source_repository,artifact_repository=artifact_repository)
    return context
