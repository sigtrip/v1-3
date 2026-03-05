# Security Policy

## Supported Versions

Currently supported versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.3.x   | :white_check_mark: |
| < 1.3   | :x:                |

## Security Features

### Encryption
- **Algorithm:** AES-256-GCM (AEAD)
- **Key Storage:** `config/master.key` (32 bytes, auto-generated)
- **Nonce:** 96-bit unique per operation
- **Fallback:** Fernet for backward compatibility

### Authentication
- **Method:** SHA-256 hash comparison
- **Protection:** Constant-time comparison (`hmac.compare_digest`)
- **Rate Limiting:** 5 attempts, 60-second cooldown
- **Thread-Safe:** Yes

### Environment Variables
All sensitive credentials must be stored in `.env` file:
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `ARGOS_NETWORK_SECRET` - **MUST be unique per installation**
- `ARGOS_MASTER_KEY` - Administrator authentication

**CRITICAL:** Never commit `.env` to version control. Use `.env.example` as template.

### Secure Configuration

1. **Generate Unique Secrets:**
   ```bash
   # Generate ARGOS_NETWORK_SECRET
   openssl rand -hex 32
   
   # Generate ARGOS_MASTER_KEY
   openssl rand -hex 32
   ```

2. **Protect Sensitive Files:**
   - `config/master.key` - encryption key
   - `config/node_id` - node identifier
   - `config/node_birth` - node creation timestamp
   - `.env` - all API keys and secrets

3. **File Permissions:**
   ```bash
   chmod 600 .env
   chmod 600 config/master.key
   ```

## Reporting a Vulnerability

We take security vulnerabilities seriously. Please follow responsible disclosure:

### How to Report

1. **DO NOT** create a public GitHub issue for security vulnerabilities
2. Email security details to: **seva1691@mail.ru**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment:** Within 48 hours
- **Initial Assessment:** Within 7 days
- **Status Updates:** Every 14 days until resolution
- **Fix Timeline:** Critical issues within 30 days, others within 90 days

### Disclosure Policy

- We will credit reporters (unless anonymity requested)
- Public disclosure only after fix is released
- CVE assignment for critical vulnerabilities

## Security Best Practices

### For Developers

1. **Never hardcode secrets** in source code
2. **Use `.env.example`** for documentation, not real credentials
3. **Validate all user inputs** before processing
4. **Use parameterized queries** for database operations
5. **Keep dependencies updated** - run `pip-audit` regularly
6. **Review code** before merging PRs

### For Users

1. **Generate unique secrets** for each installation
2. **Keep `.env` secure** - never share or commit
3. **Update regularly** to latest version
4. **Use strong master key** for authentication
5. **Monitor logs** for suspicious activity
6. **Enable firewall** for P2P network ports

### Docker Security

1. **Don't run as root** inside containers
2. **Use secrets management** instead of environment variables
3. **Scan images** for vulnerabilities
4. **Limit container capabilities**
5. **Use read-only filesystems** where possible

## Known Security Considerations

### P2P Network
- **Encryption:** HMAC-based message authentication
- **Trust Model:** Authority-based (node age + power)
- **Ports:** 55771 (TCP/UDP) - configure firewall appropriately

### Android APK
- **Permissions:** Review `buildozer.spec` for required permissions
- **Storage:** Sensitive data stored in app-private directory
- **Network:** All API calls over HTTPS

### Third-Party APIs
- **Gemini API:** HTTPS only, API key in headers
- **Telegram Bot:** HTTPS webhooks recommended
- **LM Studio:** Local network only by default

## Security Checklist

Before deploying to production:

- [ ] Generated unique `ARGOS_NETWORK_SECRET`
- [ ] Generated unique `ARGOS_MASTER_KEY`
- [ ] Verified `.env` not in version control
- [ ] Set proper file permissions (600 for secrets)
- [ ] Reviewed firewall rules for P2P ports
- [ ] Enabled HTTPS for web dashboard
- [ ] Configured rate limiting for APIs
- [ ] Set up log monitoring
- [ ] Tested backup/restore procedures
- [ ] Documented incident response plan

## Security Tools

### Automated Scanning
- **pip-audit:** Dependency vulnerability scanning (in CI/CD)
- **Bandit:** Python security linter (recommended)
- **Safety:** Check Python dependencies (recommended)

### Manual Review
- Code review all security-critical changes
- Regular security audits (quarterly recommended)
- Penetration testing for production deployments

## Compliance

### Data Protection
- **GDPR:** User data stored locally, no cloud sync by default
- **Encryption:** At-rest encryption for sensitive config
- **Retention:** Logs rotated, old data purged

### Logging
- Security events logged to `logs/argos.log`
- Authentication attempts logged
- API key usage NOT logged (security)

## Updates and Patches

### Security Updates
- Critical: Immediate hotfix release
- High: Patch within 7 days
- Medium: Patch within 30 days
- Low: Included in next regular release

### Update Process
```bash
# Check for updates
git fetch origin
git log HEAD..origin/main --oneline

# Apply updates
git pull origin main
pip install -r requirements.txt --upgrade

# Verify integrity
python health_check.py
```

## Contact

- **Security Issues:** seva1691@mail.ru
- **General Support:** GitHub Issues
- **Project Lead:** Всеволод (@sigtrip)

---

**Last Updated:** March 5, 2026  
**Version:** 1.3
