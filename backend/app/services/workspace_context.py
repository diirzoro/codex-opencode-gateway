"""Read-only owned sign-in context; never starts a runtime or creates files."""
from sqlalchemy import select
from ..models import Project, Workspace, WorkspaceSession
from . import workspaces, session_lifecycle


def restore(db, user, preferred_workspace=None, preferred_session=None):
    rows=list(db.scalars(select(Workspace).join(Project,Project.id==Workspace.project_id).where(
        Workspace.user_id==user.id,Project.user_id==user.id,Project.archived_at.is_(None)
    ).order_by(Workspace.last_activity_at.desc(),Workspace.created_at.desc())))
    if preferred_workspace:
        rows.sort(key=lambda row:row.id!=preferred_workspace)
    for workspace in rows:
        payload=workspaces.workspace_payload(workspace)
        if not payload['files_available']:continue
        sessions=list(db.scalars(select(WorkspaceSession).where(
            WorkspaceSession.workspace_id==workspace.id,WorkspaceSession.user_id==user.id
        ).order_by(WorkspaceSession.created_at.desc())))
        states=session_lifecycle.states(db,sessions)
        sessions=[row for row in sessions if states[row.id] in {'active','closed'}]
        # A live/open conversation takes precedence over an old closed selection.
        sessions.sort(key=lambda row:(states[row.id]!='active',row.id!=preferred_session))
        session=sessions[0] if sessions else None
        return {'project':workspaces.project_payload(workspace.project),'workspace':payload,
                'session':({**session_lifecycle.payload(session,states[session.id]),
                            'runtime_id':session.opencode_session_id} if session else None)}
    return {'project':None,'workspace':None,'session':None}
