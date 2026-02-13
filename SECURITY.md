# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in zapista, please report it by:

1. **DO NOT** open a public GitHub issue
2. Create a private security advisory on GitHub or contact the repository maintainers
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We aim to respond to security reports within 48 hours.

## Security Best Practices

### 1. API Key Management

**CRITICAL**: Never commit API keys to version control.

```bash
# ✅ Good: Store in config file with restricted permissions
chmod 600 ~/.zapista/config.json

# ❌ Bad: Hardcoding keys in code or committing them
```

**Recommendations:**
- Store API keys in `~/.zapista/config.json` with file permissions set to `0600`
- Consider using environment variables for sensitive keys
- Use OS keyring/credential manager for production deployments
- Rotate API keys regularly
- Use separate API keys for development and production

### 2. API (FastAPI) Authentication and CORS

**Production:** Set `API_SECRET_KEY` in the environment. All data endpoints (`/users`, `/users/{id}/lists`, `/users/{id}/events`, `/audit`) then require the `X-API-Key` header with the same value. The `/health` endpoint uses `HEALTH_CHECK_TOKEN` only (for orchestrators).

- Leave `API_SECRET_KEY` unset only in development.
- Use a long, random value (e.g. `openssl rand -hex 32`).
- **CORS:** Set `CORS_ORIGINS` to your frontend origin(s), comma-separated (e.g. `https://app.example.com`). Default `*` allows any origin (development only).

### 3. Channel Access Control

**IMPORTANT**: Always configure `allowFrom` lists for production use.

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "bridge_url": "ws://localhost:3001",
      "allowFrom": ["5511999999999"]
    }
  }
}
```

**Security Notes:**
- Empty `allowFrom` list will **ALLOW ALL** users (open by default for personal use)
- Use full phone numbers with country code for WhatsApp (e.g. 5511999999999)
- Review access logs regularly for unauthorized access attempts

### 3.1 Data Isolation Between Users (Multi-tenant)

To prevent data leakage between users, every user-visible resource is scoped by **chat_id** (e.g. WhatsApp JID / phone):

| Resource | Isolation |
|----------|-----------|
| **Sessions** | `session_key = channel:chat_id`; one JSONL file per key under `~/.zapista/sessions/` (safe filename, no path traversal). |
| **Cron (lembretes)** | Jobs store `payload.to = chat_id`. List and remove only show/allow jobs where `payload.to == current chat_id`. |
| **Lists / List items** | DB: `List.user_id` from `get_or_create_user(chat_id)`. All queries filter by `user_id`. |
| **Events** | DB: `Event.user_id` from `get_or_create_user(chat_id)`. Same for ICS import. |
| **Reminder history** | DB: `ReminderHistory.user_id`; all reads/writes use `get_or_create_user(chat_id)`. |
| **User prefs** | Language, timezone, city, quiet window, etc.: keyed by `chat_id` (via User.phone_hash). |
| **Memory** | `MemoryStore` uses `session_key` (channel:chat_id); each user has `workspace/memory/<safe_key>/MEMORY.md` and daily notes. |
| **Confirmations** | Pending state keyed by `(channel, chat_id)`. |
| **Rate limit** | Per `(channel, chat_id)`. |

Handlers and tools always call `set_context(channel, chat_id)` before executing; DB queries use `user_id` from `get_or_create_user(db, chat_id)`. Session file names are sanitized with `safe_filename()` (no `..`, `/`, `\`, or other path-unsafe characters).

### 3.2 God Mode (comandos admin)

Comandos admin (`#status`, `#users`, etc.) são protegidos por senha (`GOD_MODE_PASSWORD`):

- **Ativação:** `#<senha>` no chat ativa god-mode para esse chat (TTL 24 h).
- **Senha errada:** Silêncio total (não vaza superfície de admin).
- **Rate-limit / lockout:** Após 5 tentativas de senha errada por chat, o chat fica bloqueado 15 min. Configurável via `GOD_MODE_MAX_ATTEMPTS` e `GOD_MODE_LOCKOUT_MINUTES`.
- **Estado:** God-mode ativo em memória (perde-se em restart); lockout persiste em `~/.zapista/security/god_mode_lockout.json`. Comando `#lockout` lista bloqueios.

### 4. File System Access

File operations have path traversal protection, but:

- ✅ Run zapista with a dedicated user account
- ✅ Use filesystem permissions to protect sensitive directories
- ✅ Regularly audit file operations in logs
- ❌ Don't give unrestricted access to sensitive files

### 5. Network Security

**API Calls:**
- All external API calls use HTTPS by default
- Timeouts are configured to prevent hanging requests
- Consider using a firewall to restrict outbound connections if needed

**WhatsApp Bridge:**
- The bridge runs on `localhost:3001` by default
- If exposing to network, use proper authentication and TLS
- Keep authentication data in `~/.zapista/whatsapp-auth` secure (mode 0700)

### 6. Dependency Security

**Critical**: Keep dependencies updated!

```bash
# Check for vulnerable dependencies
pip install pip-audit
pip-audit

# Update to latest secure versions
pip install --upgrade zapista
```

For Node.js dependencies (WhatsApp bridge):
```bash
cd bridge
npm audit
npm audit fix
```

**Important Notes:**
- Keep `litellm` updated to the latest version for security fixes
- We've updated `ws` to `>=8.17.1` to fix DoS vulnerability
- Run `pip-audit` or `npm audit` regularly
- Subscribe to security advisories for zapista and its dependencies

### 7. Production Deployment

For production use:

1. **Isolate the Environment**
   ```bash
   # Run in a container or VM
   docker run --rm -it python:3.11
   pip install zapista
   ```

2. **Use a Dedicated User**
   ```bash
   sudo useradd -m -s /bin/bash zapista
   sudo -u zapista zapista gateway
   ```

3. **Set Proper Permissions**
   ```bash
   chmod 700 ~/.zapista
   chmod 600 ~/.zapista/config.json
   chmod 700 ~/.zapista/whatsapp-auth
   ```

4. **Enable Logging**
   ```bash
   # Configure log monitoring
   tail -f ~/.zapista/logs/zapista.log
   ```

5. **Use Rate Limiting**
   - Configure rate limits on your API providers
   - Monitor usage for anomalies
   - Set spending limits on LLM APIs

6. **Regular Updates**
   ```bash
   # Check for updates weekly
   pip install --upgrade zapista
   ```

### 8. Development vs Production

**Development:**
- Use separate API keys
- Test with non-sensitive data
- Enable verbose logging
- Use a test WhatsApp number

**Production:**
- Use dedicated API keys with spending limits
- Restrict file system access
- Enable audit logging
- Regular security reviews
- Monitor for unusual activity

### 9. Data Privacy

- **Logs may contain sensitive information** - secure log files appropriately
- **LLM providers see your prompts** - review their privacy policies
- **Chat history is stored locally** - protect the `~/.zapista` directory
- **API keys are in plain text** - use OS keyring for production

### 10. Incident Response

If you suspect a security breach:

1. **Immediately revoke compromised API keys**
2. **Review logs for unauthorized access**
   ```bash
   grep "Access denied" ~/.zapista/logs/zapista.log
   ```
3. **Check for unexpected file modifications**
4. **Rotate all credentials**
5. **Update to latest version**
6. **Report the incident** to maintainers

## Security Features

### Built-in Security Controls

✅ **Input Validation**
- Path traversal protection on file operations
- Dangerous command pattern detection
- Input length limits on HTTP requests

✅ **Authentication**
- Allow-list based access control
- Failed authentication attempt logging
- Open by default (configure allowFrom for production use)

✅ **Resource Protection**
- Command execution timeouts (60s default)
- Output truncation (10KB limit)
- HTTP request timeouts (10-30s)

✅ **Secure Communication**
- HTTPS for all external API calls
- WebSocket security for WhatsApp bridge

## Known Limitations

⚠️ **Current Security Limitations:**

1. **No Rate Limiting** - Users can send unlimited messages (add your own if needed)
2. **Plain Text Config** - API keys stored in plain text (use keyring for production)
3. **No Session Management** - No automatic session expiry
4. **Limited Command Filtering** - Only blocks obvious dangerous patterns
5. **No Audit Trail** - Limited security event logging (enhance as needed)

## Security Checklist

Before deploying zapista:

- [ ] API keys stored securely (not in code)
- [ ] Config file permissions set to 0600
- [ ] `allowFrom` lists configured for all channels
- [ ] Running as non-root user
- [ ] File system permissions properly restricted
- [ ] Dependencies updated to latest secure versions
- [ ] Logs monitored for security events
- [ ] Rate limits configured on API providers
- [ ] Backup and disaster recovery plan in place
- [ ] Security review of custom skills/tools

## Updates

**Last Updated**: 2026-02-03

For the latest security updates and announcements, check:
- GitHub Security Advisories: https://github.com/rafae/zapista/security/advisories
- Release Notes: https://github.com/rafae/zapista/releases

## License

See LICENSE file for details.
