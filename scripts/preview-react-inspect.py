"""Read-only inventory of the existing test account's preview readiness.

Never runs project scripts, npm, Docker or source code. Never prints project
paths, IDs, source, dependency URLs, script commands or credentials.
"""
import json
import os
from pathlib import Path

KNOWN_DEPENDENCIES={'react','react-dom','vite','next','vue','svelte','@angular/core'}
KNOWN_SCRIPTS={'build','dev','preview','start','test'}

def summarize_manifest(value):
    if not isinstance(value,dict):
        raise ValueError('Manifest must be an object')
    dependencies={}
    for key in ('dependencies','devDependencies'):
        if isinstance(value.get(key),dict): dependencies.update(value[key])
    scripts=value.get('scripts')
    names=set(dependencies)
    framework=('nextjs' if 'next' in names else 'vite' if 'vite' in names
               else 'react' if 'react' in names else 'other')
    return {'framework':framework,
            'known_dependencies':sorted(names & KNOWN_DEPENDENCIES),
            'standard_scripts':sorted(set(scripts) & KNOWN_SCRIPTS) if isinstance(scripts,dict) else [],
            'project_commands_executed':False}

def main():
    if os.geteuid()!=0: raise SystemExit('Protected operator context required')
    app=Path('/home/tahir/opencode-gateway')
    for row in (app/'.env').read_text().splitlines():
        if '=' in row and not row.lstrip().startswith('#'):
            key,value=row.split('=',1)
            os.environ[key.strip()]=value.strip().strip('"').strip("'")
    import sys
    sys.path.insert(0,str(app/'backend'))
    from sqlalchemy import select,text
    from app.database import SessionLocal
    from app.models import Project,Workspace,User
    from app.services.workspaces import safe_path
    reports=[]
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        rows=db.scalars(select(Workspace).join(Project,Workspace.project_id==Project.id)
             .join(User,Workspace.user_id==User.id)
             .where(User.username=='testuser',Project.user_id==User.id,
                    Project.archived_at.is_(None),Workspace.status=='ready').limit(20)).all()
        for number,workspace in enumerate(rows,1):
            manifest=safe_path(workspace,'package.json')
            if not manifest.is_file(): continue
            if manifest.stat().st_size>250000:
                reports.append({'candidate':number,'state':'manifest_exceeds_limit'});continue
            try:
                result=summarize_manifest(json.loads(manifest.read_text(encoding='utf-8')))
            except (ValueError,UnicodeError):
                reports.append({'candidate':number,'state':'invalid_manifest'});continue
            if result['framework'] not in {'react','vite','nextjs'}: continue
            result.update(candidate=number,
                lockfiles=[name for name in ['package-lock.json','pnpm-lock.yaml','yarn.lock']
                           if safe_path(workspace,name).is_file()],
                existing_outputs=[name for name in ['dist/index.html','build/index.html','out/index.html']
                                  if safe_path(workspace,name).is_file()])
            reports.append(result)
    print(json.dumps({'read_only':True,'scope':'existing test account only',
                      'react_candidates':reports},sort_keys=True))

if __name__=='__main__': main()
