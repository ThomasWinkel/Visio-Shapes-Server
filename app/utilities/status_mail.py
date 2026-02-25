from datetime import datetime, timedelta
from sqlalchemy import func
from app.models.auth import User
from app.models.visio import Shape, Stencil, ShapeDownload, StencilDownload
from app.extensions import db, mail
from flask import current_app
from flask_mail import Message


def send_status_mail():
    """Query last-24h stats and send a status e-mail to OWNER_EMAIL."""
    owner_email = current_app.config.get('OWNER_EMAIL', '')
    if not owner_email:
        current_app.logger.warning('send_status_mail: OWNER_EMAIL not set – skipping.')
        return

    since = datetime.utcnow() - timedelta(hours=24)
    date_str = datetime.utcnow().strftime('%Y-%m-%d')

    # ── New users ─────────────────────────────────────────────────────────────
    new_users = (
        User.query
        .filter(User.register_date >= since)
        .order_by(User.register_date)
        .all()
    )

    # ── Per-user activity maps (user_id → count) ──────────────────────────────
    shapes_added = dict(
        db.session.query(Shape.user_id, func.count(Shape.id))
        .filter(Shape.upload_date >= since)
        .group_by(Shape.user_id)
        .all()
    )
    stencils_added = dict(
        db.session.query(Stencil.user_id, func.count(Stencil.id))
        .filter(Stencil.upload_date >= since)
        .group_by(Stencil.user_id)
        .all()
    )
    shapes_used = dict(
        db.session.query(ShapeDownload.user_id, func.count(ShapeDownload.id))
        .filter(ShapeDownload.date >= since)
        .group_by(ShapeDownload.user_id)
        .all()
    )
    stencils_dl = dict(
        db.session.query(StencilDownload.user_id, func.count(StencilDownload.id))
        .filter(StencilDownload.date >= since)
        .group_by(StencilDownload.user_id)
        .all()
    )

    # ── Build active-user rows (any non-zero activity) ────────────────────────
    active_ids = set(shapes_added) | set(stencils_added) | set(shapes_used) | set(stencils_dl)
    active_users = []
    for uid in active_ids:
        user = db.session.get(User, uid)
        if not user:
            continue
        active_users.append({
            'name':              user.name,
            'shapes_added':      shapes_added.get(uid, 0),
            'stencils_added':    stencils_added.get(uid, 0),
            'shapes_used':       shapes_used.get(uid, 0),
            'stencils_dl':       stencils_dl.get(uid, 0),
        })
    active_users.sort(key=lambda u: -(
        u['shapes_added'] + u['stencils_added'] + u['shapes_used'] + u['stencils_dl']
    ))

    msg = Message(
        subject=f'Visio Shapes – Daily Status {date_str}',
        recipients=[owner_email],
        html=_build_html(date_str, new_users, active_users),
    )
    mail.send(msg)
    current_app.logger.info('send_status_mail: sent to %s', owner_email)


# ── HTML builder ──────────────────────────────────────────────────────────────

_TH  = 'padding:6px 10px; font-weight:600; white-space:nowrap; text-align:left;'
_THR = 'padding:6px 10px; font-weight:600; white-space:nowrap; text-align:right;'
_TD  = 'padding:5px 10px; border-top:1px solid #eee;'
_TDR = 'padding:5px 10px; border-top:1px solid #eee; text-align:right;'


def _build_html(date_str, new_users, active_users):
    # New-users section
    if new_users:
        items = ''.join(
            f'<li style="margin:2px 0;">{u.name} &lt;{u.email}&gt;</li>'
            for u in new_users
        )
        new_section = f'<ul style="margin:4px 0 0 0; padding-left:18px;">{items}</ul>'
    else:
        new_section = '<p style="margin:4px 0 0 0; color:#aaa;">–</p>'

    # Active-users table
    if active_users:
        rows = ''
        for i, u in enumerate(active_users):
            bg = '#f9f8f6' if i % 2 == 0 else '#ffffff'
            rows += (
                f'<tr style="background:{bg};">'
                f'<td style="{_TD}">{u["name"]}</td>'
                f'<td style="{_TDR}">{u["shapes_added"]}</td>'
                f'<td style="{_TDR}">{u["stencils_added"]}</td>'
                f'<td style="{_TDR}">{u["shapes_used"]}</td>'
                f'<td style="{_TDR}">{u["stencils_dl"]}</td>'
                f'</tr>'
            )
        active_section = f'''
        <table style="border-collapse:collapse; width:100%; font-size:13px;">
          <thead>
            <tr style="background:#e8e4de;">
              <th style="{_TH}">Name</th>
              <th style="{_THR}">Shapes +</th>
              <th style="{_THR}">Stencils +</th>
              <th style="{_THR}">Shapes genutzt</th>
              <th style="{_THR}">Stencils DL</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>'''
    else:
        active_section = '<p style="color:#aaa;">–</p>'

    return f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:'Helvetica Neue',Arial,sans-serif; font-size:14px; color:#3b3530; background:#fff; padding:24px; max-width:640px;">
  <h2 style="margin:0 0 4px 0; font-size:18px;">Visio Shapes – Daily Status</h2>
  <p style="margin:0 0 24px 0; color:#999; font-size:12px;">{date_str} &nbsp;|&nbsp; letzte 24 Stunden (UTC)</p>

  <h3 style="margin:0 0 6px 0; font-size:13px; text-transform:uppercase; letter-spacing:.05em; color:#888; border-bottom:1px solid #e0dbd4; padding-bottom:4px;">
    Neue User ({len(new_users)})
  </h3>
  {new_section}

  <h3 style="margin:24px 0 6px 0; font-size:13px; text-transform:uppercase; letter-spacing:.05em; color:#888; border-bottom:1px solid #e0dbd4; padding-bottom:4px;">
    Aktive User ({len(active_users)})
  </h3>
  {active_section}

  <p style="margin:28px 0 0 0; font-size:11px; color:#bbb;">visio-shapes.com</p>
</body>
</html>'''
