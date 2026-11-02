"""Local sandbox grant state; every protected request is checked before ATS I/O."""
from dataclasses import dataclass
from datetime import datetime


def utc_instant(value):
    if not isinstance(value, str):
        raise ValueError('UTC instant required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError('UTC instant required')
    return result


@dataclass(frozen=True)
class Grant:
    grant_id: str
    principal: str
    valid_from: str
    valid_until: str
    revoked_at: str | None = None

    def __post_init__(self):
        if not self.grant_id or not self.principal:
            raise ValueError('grant and principal identities required')
        if utc_instant(self.valid_from) >= utc_instant(self.valid_until):
            raise ValueError('nonempty grant validity interval required')
        if self.revoked_at is not None:
            utc_instant(self.revoked_at)

    def decision(self, principal, now):
        observed = utc_instant(now)
        if principal != self.principal:
            return 'principal_mismatch'
        if observed < utc_instant(self.valid_from):
            return 'not_yet_valid'
        if observed >= utc_instant(self.valid_until):
            return 'expired'
        if self.revoked_at is not None and observed >= utc_instant(self.revoked_at):
            return 'revoked'
        return 'allowed'

    def revoke(self, now):
        utc_instant(now)
        if self.revoked_at is not None:
            return self
        return Grant(self.grant_id, self.principal, self.valid_from,
                     self.valid_until, now)

    def observation(self, principal, now):
        return dict(grantId=self.grant_id, principalId=principal,
                    validFrom=self.valid_from, validUntil=self.valid_until,
                    revokedAt=self.revoked_at, authorizedAt=now,
                    reason=self.decision(principal, now))
