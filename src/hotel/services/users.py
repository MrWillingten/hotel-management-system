"""Staff accounts: created and managed by managers; passwords changed by their owners."""

from __future__ import annotations

from hotel.domain.actor import Actor
from hotel.domain.clock import Clock
from hotel.domain.enums import Role
from hotel.domain.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    StaleDataError,
    ValidationError,
)
from hotel.domain.passwords import PasswordPolicy
from hotel.domain.removal import RemovalAction, RemovalPlan, plan_removal
from hotel.domain.users import User, validate_full_name, validate_username
from hotel.persistence.unit_of_work import UnitOfWork, UnitOfWorkFactory
from hotel.services.audit import record
from hotel.services.auth import hash_token
from hotel.services.authorization import require_role
from hotel.services.passwords import PasswordHasher


class UserService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        hasher: PasswordHasher,
        password_policy: PasswordPolicy,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._hasher = hasher
        self._policy = password_policy

    # ------------------------------------------------------------ reading
    def list_users(self, actor: Actor, *, archived: bool = False) -> list[User]:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            return uow.users.list_all(archived=archived)

    # ------------------------------------------------------------ delete or archive (6.17)
    def count_archived(self, actor: Actor) -> int:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            return uow.users.count_archived()

    def removal_plan(self, actor: Actor, user_id: int) -> RemovalPlan:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            return self._removal(uow, actor, self._load(uow, user_id))

    def remove(self, actor: Actor, user_id: int) -> RemovalAction:
        """Delete an account that never did anything; archive one with a history.

        The audit log refers to every person who acted, so their account stays
        (archived, deactivated, signed out everywhere).
        """
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            user = self._load(uow, user_id)
            plan = self._removal(uow, actor, user)
            if not plan.allowed:
                raise BusinessRuleViolation(plan.blocked)
            action = plan.action
            if action is RemovalAction.DELETE and not uow.users.delete(user_id):
                action = RemovalAction.ARCHIVE  # something still refers to it after all
            if action is RemovalAction.ARCHIVE and not user.is_archived:
                uow.users.archive(user_id, self._clock.now())
                uow.sessions.delete_for_user(user_id)
            record(
                uow,
                self._clock,
                actor,
                "user.deleted" if action is RemovalAction.DELETE else "user.archived",
                entity="user",
                entity_id=user_id,
                username=user.username,
            )
            return action

    def restore(self, actor: Actor, user_id: int) -> User:
        """Back in the staff list, still deactivated until a manager reactivates it."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            user = self._load(uow, user_id)
            if user.is_archived:
                uow.users.archive(user_id, None)
                record(uow, self._clock, actor, "user.restored", entity="user", entity_id=user_id)
            return uow.users.get(user_id)

    @staticmethod
    def _removal(uow: UnitOfWork, actor: Actor, user: User) -> RemovalPlan:
        blocked = None
        if user.id == actor.user_id:
            blocked = "user.cannot_remove_self"
        elif user.is_manager and user.is_active and uow.users.count_active_managers() <= 1:
            blocked = "user.last_manager"
        return plan_removal(uow.users.count_actions(user.id), blocked=blocked)

    def get_user(self, actor: Actor, user_id: int) -> User:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            return self._load(uow, user_id)

    # ------------------------------------------------------------ managing accounts
    def create_user(
        self,
        actor: Actor,
        *,
        username: str,
        full_name: str,
        role: Role,
        temporary_password: str,
    ) -> User:
        """New accounts must choose their own password at their first sign-in."""
        require_role(actor, Role.MANAGER)
        username = validate_username(username)
        full_name = validate_full_name(full_name)
        self._policy.check(temporary_password, username=username)
        with self._uow() as uow:
            if uow.users.get_by_username(username) is not None:
                raise ConflictError(
                    "user.username_taken", fields={"username": "user.username_taken"}
                )
            user = uow.users.add(
                User(
                    id=None,
                    username=username,
                    full_name=full_name,
                    password_hash=self._hasher.hash(temporary_password),
                    role=Role(role),
                    must_change_password=True,
                    created_at=self._clock.now(),
                )
            )
            record(
                uow,
                self._clock,
                actor,
                "user.created",
                entity="user",
                entity_id=user.id,
                role=user.role.value,
            )
            return user

    def update_user(
        self, actor: Actor, user_id: int, *, version: int, full_name: str, role: Role
    ) -> User:
        require_role(actor, Role.MANAGER)
        full_name = validate_full_name(full_name)
        role = Role(role)
        with self._uow() as uow:
            user = self._load_for_change(uow, user_id, version)
            if user.role is Role.MANAGER and role is not Role.MANAGER and user.is_active:
                self._keep_one_manager(uow)
            changed = [
                name
                for name, old, new in (
                    ("full_name", user.full_name, full_name),
                    ("role", user.role, role),
                )
                if old != new
            ]
            user.full_name, user.role = full_name, role
            uow.users.update(user)
            record(
                uow,
                self._clock,
                actor,
                "user.updated",
                entity="user",
                entity_id=user.id,
                fields=changed,
                role=role.value,
            )
            return user

    def set_active(self, actor: Actor, user_id: int, *, version: int, active: bool) -> User:
        """Deactivating an account also ends all of its sessions immediately."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            user = self._load_for_change(uow, user_id, version)
            if user.is_active == active:
                return user
            if not active:
                if user.id == actor.user_id:
                    raise BusinessRuleViolation("user.cannot_deactivate_self")
                if user.role is Role.MANAGER:
                    self._keep_one_manager(uow)
            user.is_active = active
            uow.users.update(user)
            if not active:
                uow.sessions.delete_for_user(user.id)
            record(
                uow,
                self._clock,
                actor,
                "user.activated" if active else "user.deactivated",
                entity="user",
                entity_id=user.id,
            )
            return user

    def reset_password(self, actor: Actor, user_id: int, *, temporary_password: str) -> User:
        """Set a temporary password; the owner must replace it at the next sign-in."""
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            user = self._load_for_change(uow, user_id)
            self._policy.check(temporary_password, username=user.username)
            user.password_hash = self._hasher.hash(temporary_password)
            user.must_change_password = True
            user.register_successful_login()  # clears failures and any lock
            uow.users.update(user)
            uow.sessions.delete_for_user(user.id)
            record(uow, self._clock, actor, "user.password_reset", entity="user", entity_id=user.id)
            return user

    def unlock(self, actor: Actor, user_id: int) -> User:
        require_role(actor, Role.MANAGER)
        with self._uow() as uow:
            user = self._load_for_change(uow, user_id)
            user.register_successful_login()
            uow.users.update(user)
            record(uow, self._clock, actor, "user.unlocked", entity="user", entity_id=user.id)
            return user

    # ------------------------------------------------------------ own account
    def change_own_password(
        self,
        actor: Actor,
        *,
        current_password: str,
        new_password: str,
        current_token: str | None = None,
    ) -> User:
        """Change the signed-in user's password and end their *other* sessions."""
        if actor.user is None:
            raise PermissionDeniedError
        with self._uow() as uow:
            user = self._load(uow, actor.user.id)
            # These strings are error codes, not passwords (bandit B105 false positive).
            if not self._hasher.verify(current_password, user.password_hash):
                code = "password.current_wrong"  # nosec B105
                raise ValidationError(code, fields={"current_password": code})
            if new_password == current_password:
                code = "password.same_as_current"  # nosec B105
                raise ValidationError(code, fields={"password": code})
            self._policy.check(new_password, username=user.username)
            user.password_hash = self._hasher.hash(new_password)
            user.must_change_password = False
            uow.users.update(user)
            if current_token:
                uow.sessions.delete_for_user_except(user.id, hash_token(current_token))
            else:
                uow.sessions.delete_for_user(user.id)
            record(
                uow, self._clock, actor, "user.password_changed", entity="user", entity_id=user.id
            )
            return user

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _load(uow: UnitOfWork, user_id: int, version: int | None = None) -> User:
        user = uow.users.get(user_id)
        if user is None:
            raise NotFoundError(entity="user", id=user_id)
        if version is not None and user.version != version:
            raise StaleDataError(entity="user", id=user_id)
        return user

    @classmethod
    def _load_for_change(cls, uow: UnitOfWork, user_id: int, version: int | None = None) -> User:
        user = cls._load(uow, user_id, version)
        if user.is_archived:
            raise BusinessRuleViolation("user.archived")
        return user

    @staticmethod
    def _keep_one_manager(uow: UnitOfWork) -> None:
        """The hotel must never be left without an active manager."""
        if uow.users.count_active_managers() <= 1:
            raise BusinessRuleViolation("user.last_manager")
