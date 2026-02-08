# MODULE 10: USER ACL & SECURITY ARCHITECTURE

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (SecOps Engineer)
> **Word Count Target:** >3000 Words
> **Scope:** Identity Management. Killing the shared root password, enforcing 2FA, and granular API permissions.

---

# 1. The Identity Crisis

By default, Proxmox implies you log in as `root@pam` with a password.
**This is unacceptable for Goliath.**
*   **Risk:** Verifyable Identity. If `root` deletes a VM, *who* physically pressed the button? Was it the Senior Eng? The Junior? Or a Hacker?
*   **Solution:** Named Users + 2FA + Least Privilege.

## 1.1 Authentication Realms
Proxmox supports multiple identity backends.
*   **Linux PAM (`pam`):** Uses the Host OS users (`/etc/passwd`).
    *   *Pros:* Integrated with OS SSH access.
    *   *Cons:* Managing users requires shell access.
*   **Proxmox VE (`pve`):** Internal database users.
    *   *Pros:* Virtual users. No shell access on the host. Perfect for "Operators".
*   **LDAP / OpenID Connect:** Enterprise integration.

**Goliath Policy:**
*   **Admins:** Use `pam` (Must natively exist on Linux for SSH).
*   **Operators/Auditors:** Use `pve` (No shell access).

---

# 2. Two-Factor Authentication (2FA)

Passwords are dead. You must enforce 2FA.

## 2.1 TOTP (Time-based One-Time Password)
Standard Google/Microsoft Authenticator.
*   **Enforcement:** You can enforce this at the **Realm** level.
*   **Step-by-Step:**
    1.  Datacenter -> Permissions -> Two Factor -> Add -> TOTP.
    2.  Scan QR Code.
    3.  **Critical:** User must verify code to enable it.

## 2.2 WebAuthn (YubiKey / Passkey)
Hardware-backed security.
*   **Phishing Resistant:** Unlike TOTP, WebAuthn domain-binds the credential. A fake phishing site cannot steal the token.
*   **Goliath Requirement:** Root account **MUST** use YubiKey/WebAuthn if physical access allows.

## 2.3 The "Lockout" Recovery
If you lose your 2FA, you are locked out of the GUI.
*   **The Backdoor:** SSH.
*   **Recovery Command:**
    ```bash
    # Unlock a user (Emergency only)
    pveum user modify root@pam --delete-second-factors
    ```
    *   *Audit:* This command logs to `/var/log/syslog`.

---

# 3. API Tokens: The Automation Key

Never put a password in a Terraform script. Passwords expire. Passwords require 2FA (which breaks scripts).
**API Tokens** are the service account equivalent.

## 3.1 Token Types
*   **Privilege Separation:** You can create a token `root@pam!terraform` that has *less* permission than the user `root@pam`.
*   **Fixed Secret:** The secret is shown **once**. It never changes.

## 3.2 Creating the Goliath Terraform Token
1.  **User:** Create a dedicated user `terraform@pve`. (Do not attach it to root).
2.  **Permissions:** Assign `PVEVMAdmin` role.
3.  **Token:** Generate `terraform@pve!automation`.
4.  **Scope:**
    *   User `terraform@pve`: Blocked (No password set). Cannot login to GUI.
    *   Token `!automation`: Active. Can only be used via API.

---

# 4. The Permission Graph (ACLs)

Proxmox permissions are tri-dimensional: **User + Role + Path**.

## 4.1 Roles (The "What")
*   `Administrator`: God mode.
*   `PVEVMAdmin`: Can Create/Delete/Migrate VMs.
*   `PVEVMUser`: Can Start/Stop/Console (Cannot Delete).
*   `PVEAuditor`: Read Only.

## 4.2 Paths (The "Where")
Permissions propagate down.
*   `/`: Global.
*   `/vms`: All VMs.
*   `/vms/100`: Only VM 100.
*   `/storage`: All Storage.
*   `/storage/local-zfs`: Only local storage.

## 4.3 Groups (The "Who")
Never assign permissions to Users. Assign to **Groups**.
*   **Group:** `Goliath-Admins` -> Role: `Administrator` on `/`.
*   **Group:** `Goliath-Auditors` -> Role: `PVEAuditor` on `/`.
*   **Group:** `Goliath-Bots` -> Role: `PVEVMUser` on `/vms/100` (The Bot can restart itself, but not the Database).

---

# 5. Resource Pools: Quotas logic

By default, an Admin can use 100% of the cluster RAM.
**Resource Pools** allow logical grouping and simple view filtering, but in Proxmox, they are also a Permission Boundary.

## 5.1 The "Dev" Pool
*   **Create Pool:** `dev-pool`.
*   **Add Resources:** VM 105, VM 106, Storage `local-lvm`.
*   **Permission:** Give Group `Junior-Devs` Admin access **only on `pool/dev-pool`**.
*   **Result:** They can Stop/Start/Delete VMs inside the pool. They cannot touch the "Production" pool.

## 5.2 The Missing Quota
*   *Warning:* Proxmox does *not* strictly enforce "Max 64GB RAM" per pool natively in the GUI (unlike VMware).
*   *Workaround:* You must manage this administratively or via custom hookscripts that check pool total usage before allowing VM start.

---

# 6. Propagation: The Inheritance Rule

When you set a permission on `/vms` with `Propagate=Yes`:
*   It applies to `/vms/100`, `/vms/101`, etc.
*   It applies to *future* VMs created in that path.

**The "Deny" Problem:**
Proxmox ACLs are **Additive**.
*   If Group A has "No Access".
*   And user Bob (in Group A) has "Admin Access".
*   **Result:** Bob has Admin Access.
*   *Rule:* You cannot "Blacklist" a user from a specific resource if they inherit permission from a parent path. You must structure your paths (Pools) to avoid overlapping scopes.

---

# 7. Audit Logs: The Black Box

Security is useless without logs.

## 7.1 The `pve-api` Log
Every action in the GUI is an API call.
*   **Location:** `/var/log/pveproxy/access.log`.
*   **Format:**
    ```
    192.168.1.50 - root@pam [08/Feb/2026:10:00:00] "POST /api2/json/nodes/pve1/qemu/100/status/stop HTTP/1.1" 200
    ```
    *   *Intelligence:* You can grep this log to see exactly *when* VM 100 was stopped and by *whom*.

## 7.2 Syslog Integration
Goliath requires these logs to be shipped instantly to a remote syslog server (Loki/Graylog) so a hacker cannot wipe their tracks after breaking in.
*   **Config:** `/etc/rsyslog.conf` -> Forward `*.*` to Log Server.

*(End of Module 10)*
