"""Read a named version's existing public model; never invent legacy six tables."""
import argparse,gzip,hashlib,json
from pathlib import Path

REGISTRY=Path(__file__).with_name('data_versions.json')


def read_public_tables(version):
    registry=json.loads(REGISTRY.read_text(encoding='utf8'))
    metadata=registry['versions'][version];tables={}
    for name,ref in metadata['public_tables'].items():
        raw=Path(ref['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('Saved data changed: '+name)
        tables[name]=json.loads(gzip.decompress(raw))
    return metadata,tables


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('version');args=parser.parse_args()
    meta,tables=read_public_tables(args.version)
    print(json.dumps(dict(data_version=args.version,six_table_model_status=meta['six_table_model_status'],
        counts={name:len(rows) for name,rows in tables.items()},model_root=meta['public_model_root'],
        data_modified=False),ensure_ascii=False,indent=2))
