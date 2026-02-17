"""
Sistema de segurança para comandos admin (God Mode).

Autorização por senha com hash; sessão com TTL.
"""

import hashlib
import os
from datetime import datetime, timedelta


class AdminSecurity:
    """Sistema de segurança para comandos admin."""

    def __init__(self) -> None:
        self._password_hash = os.getenv("GOD_MODE_PASSWORD", "")
        # Se a env tiver valor, assumir que é senha em claro e usar hash para comparação
        if self._password_hash:
            self._password_hash = self._hash_password(self._password_hash)
        self._authorized_chats: dict[str, datetime] = {}
        self._session_duration_hours = 24

    def _hash_password(self, password: str) -> str:
        """Hash da senha para comparação segura."""
        return hashlib.sha256(password.encode()).hexdigest()

    def authorize(self, chat_id: str, password: str) -> bool:
        """Autoriza um chat_id se a senha estiver correta."""
        if not self._password_hash:
            return False
        input_hash = self._hash_password(password)
        if input_hash == self._password_hash:
            self._authorized_chats[chat_id] = datetime.now()
            return True
        return False

    def is_authorized(self, chat_id: str) -> bool:
        """Verifica se chat_id está autorizado."""
        if chat_id not in self._authorized_chats:
            return False
        auth_time = self._authorized_chats[chat_id]
        if datetime.now() - auth_time > timedelta(hours=self._session_duration_hours):
            del self._authorized_chats[chat_id]
            return False
        return True

    def deauthorize(self, chat_id: str) -> None:
        """Desautoriza um chat_id."""
        if chat_id in self._authorized_chats:
            del self._authorized_chats[chat_id]

    def get_authorized_count(self) -> int:
        """Retorna número de sessões ativas."""
        return len(self._authorized_chats)


# Instância global (opcional: usar em vez do dict em backend.admin_commands)
admin_security = AdminSecurity()
