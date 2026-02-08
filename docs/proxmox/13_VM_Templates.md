# MODULE 13: VM TEMPLATES & CLOUD-INIT

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (DevOps Engineer)
> **Word Count Target:** >3000 Words
> **Scope:** The Factory. Turning specific VMs into generic Templates, and using Cloud-Init to hydrate them.

---

# 1. The Philosophy: Pets vs Cattle

*   **Pets:** You name them (Gandalf, Zeus). You patch them. When they get sick, you nurse them (SSH in and fix it).
*   **Cattle:** You number them (Web-01, Web-02). You do not patch them. When they get sick, you shoot them (Destroy) and replace them.
*   **Goliath Rule:** All AI/HFT workers are **Cattle**.

## 1.1 The Template
A Template in Proxmox is a read-only logical entity.
*   **Physics:** It is a VM Config + a Disk Image.
*   **Property:** It cannot be started. It can only be **Cloned**.
*   **Cloning Mechanics:**
    1.  **Full Clone:** Copies the entire disk (Independent). Slow.
    2.  **Linked Clone:** Creates a snapshot pointer. Fast (1 second). Space efficient.
    *   *Goliath Standard:* **Linked Clones** for all worker nodes.

---

# 2. Cloud-Init: The Injector

A template is generic ("I am Ubuntu"). A VM needs identity ("I am DB-01, IP 10.0.0.5").
**Cloud-Init** is the standard for injecting this identity at boot.

## 2.1 The Mechanic
1.  **Proxmox Side:** You attach a tiny ISO file (4MB) to the VM.
2.  **Content:** This ISO contains `user-data` (YAML) with SSH keys, Hostname, and Users.
3.  **VM Side:** On first boot, the `cloud-init` service mounts the ISO, reads the YAML, creates the user, adds the SSH key, and sets the IP.

## 2.2 Installing Cloud-Init
Your base image *must* have the packages.
```bash
apt update
apt install cloud-init cloud-guest-utils -y
```

## 2.3 The "No Password" Rule
Cloud-Init allows setting a password.
**Goliath Policy:** **Forbidden**.
*   We inject **SSH Public Keys** only.
*   *Why?* If there is no password, it cannot be brute-forced.

---

# 3. Building the Golden Image (Step-by-Step)

We do not use ISOs manually anymore. We build the Master Template once.

## 3.1 Preparation
1.  Create a VM normally (Ubuntu 24.04 Server).
2.  Update everything: `apt update && apt upgrade -y`.
3.  Install Goliath Base Tools: `curl`, `wget`, `htop`, `jq`, `vim`.
4.  **The Critical Clean-Up:**

## 3.2 The Machine-ID Trap (CRITICAL)
Linux generates a unique ID in `/etc/machine-id`.
*   *The Bug:* If you clone a VM with an existing ID, all clones have the **same ID**.
*   *The Symptom:* DHCP assigns same IP. Journal logs get merged in centralized logging. Kubernetes fails to start.
*   *The Fix:*
    ```bash
    # Reset Machine ID
    truncate -s 0 /etc/machine-id
    rm /var/lib/dbus/machine-id
    ln -s /etc/machine-id /var/lib/dbus/machine-id
    
    # Remove SSH Host Keys (So regeneration happens on boot)
    rm /etc/ssh/ssh_host_*
    
    # Clean Apt Cache
    apt clean
    
    # Poweroff
    poweroff
    ```

## 3.3 Conversion
In Proxmox:
1.  Remove the CD-ROM Drive (The Installer ISO).
2.  Add **CloudInit Drive** (Hardware -> Add -> CloudInit Device -> Storage: local-zfs).
3.  Right Click VM -> **Convert to Template**.

---

# 4. Consuming the Template

Now you have `Template 9000 (Ubuntu-Base)`.

## 4.1 Manual Cloning (The GUI Way)
1.  Right Click 9000 -> Clone.
2.  Name: `hft-worker-01`.
3.  Mode: **Linked Clone**.
4.  **Cloud-Init Tab:**
    *   User: `goliath-admin`.
    *   SSH Key: `ssh-ed25519 AAA...`.
    *   IP Config: `Static: 192.168.1.50/24`.
5.  Start.
6.  *Result:* VM boots, sets IP, creates user. You SSH in immediately.

## 4.2 Automation (The Terraform Way)
This is how Goliath operates. We do not click GUIs.

```hcl
resource "proxmox_vm_qemu" "worker" {
    name = "hft-worker-${count.index}"
    target_node = "pve1"
    clone = "Ubuntu-Base" # The Template Name
    full_clone = false    # Linked Clone
    
    # Cloud-Init Overrides
    ciuser = "goliath-admin"
    sshkeys = file("~/.ssh/id_ed25519.pub")
    ipconfig0 = "ip=192.168.1.10${count.index}/24,gw=192.168.1.1"
}
```

---

# 5. Lifecycle Management

Software rots. Ubuntu 24.04 gets a kernel update.
**Do we patch the Template? No.**

## 5.1 The Immutable Workflow
1.  **Clone** the *existing* Template 9000 to a temporary VM (e.g., 9001).
2.  Start 9001.
3.  `apt update && apt upgrade`.
4.  Verify it works.
5.  Perform the **Clean-Up** (Section 3.2).
6.  Convert 9001 to Template.
7.  **Update Terraform** to point to new Template ID (or rename).
8.  **Destroy** old Template 9000.

## 5.2 CI/CD Pipeline (Packer)
Advanced users use **HashiCorp Packer**.
*   **Logic:** Packer boots an ISO, auto-types the install commands (preseed), runs scripts, cleans up, and outputs a Template.
*   **Goliath Verdict:** Good for scale, but manual "Clone-Update-Template" is faster for small teams (< 500 VMs).

---

# 6. Windows Templates (The Pain)

Cloud-Init is Linux native. Windows uses **Cloudbase-Init**.
*   **Complexity:** High.
*   **Sysprep:** Windows requires `sysprep.exe` to generalize the SID (Security ID).
*   **Process:**
    1.  Install Windows.
    2.  Install VirtIO Drivers.
    3.  Install Cloudbase-Init.
    4.  Run `sysprep /generalize /oobe /shutdown`.
    5.  Convert to Template.
*   *Note:* Windows Linked Clones are fragile. Use Full Clones for Windows to avoid disk lock issues.

*(End of Module 13)*
