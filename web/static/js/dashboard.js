/* dashboard.js — LRN Tools Web Dashboard — vanilla JS, no frameworks */

'use strict';

/* ─────────────────────────────────────────────────────────────────────
   TIP LIBRARY
   Tips are keyed by category prefix from the tool ID (e.g. "dns",
   "freeipa", etc.), plus "general" for any page.
───────────────────────────────────────────────────────────────────── */
const TIPS = {
  general: [
    "It's always DNS. Even when it isn't DNS... it started as DNS.",
    "Have you tried turning it off and on again? I'm serious. Try it.",
    "The best backup is the one you've actually tested. When did you last test yours?",
    "Logs don't lie. People do. Always check the logs.",
    "No one has ever regretted taking a snapshot before making changes.",
    "The difference between a sysadmin and a wizard? The wizard's spells are documented.",
    "rm -rf is forever. Snapshots are not. Choose wisely.",
    "chmod 777 is not a solution. It's a cry for help.",
    "If it's stupid but it works... document it immediately.",
    "There are two types of admins: those who have lost data, and those who will.",
    "SELinux set to permissive is just a passive-aggressive audit log.",
    "That cron job that's been failing silently for six months? Yeah, it's still failing.",
    "Pro tip: grep is free. Use it before opening a ticket.",
    "systemctl status is your friend. Visit often.",
    "When in doubt, reboot. But document why first.",
    "The firewall is probably fine. Have you checked DNS?",
    "Every 'temporary' fix is permanent until something breaks.",
    "Read the man page. All of it. Yes, all of it.",
    "Trust but verify. Preferably verify first, trust later.",
    "Air-gapped doesn't mean secure. It just means slower to compromise.",
  ],
  dns: [
    "It's DNS. It's always DNS. You already knew that.",
    "Flush that DNS cache and try again. You know the drill.",
    "PTR records: because forward zones are only half the story.",
    "Zone transfer failed? Check the ACLs. Both of them.",
    "DNSSEC is great until it isn't. Then it's really, really not.",
    "Your TTL is set to what? Someone's going to regret that.",
    "named.conf has more syntax traps than a logic puzzle. Use named-checkconf.",
    "If DNS is working, don't touch it. Seriously. Walk away.",
    "Recursion: great feature, terrible if left open to the internet.",
    "Split-horizon DNS: because one view of reality is never enough in IT.",
  ],
  freeipa: [
    "Kerberos: because passwords are for people who enjoy simple lives.",
    "Have you kinit'd today? Your TGT might have expired 3 hours ago.",
    "Replication lag: not a feature, but your logs will tell you how much.",
    "LDAP is just a database that quietly judges your schema choices.",
    "If FreeIPA is down, nothing works. You already know this.",
    "ipactl status before you panic. Always ipactl status first.",
    "Certificate renewal: not optional, not 'future Mike's problem'.",
    "Two IPA replicas minimum. You wouldn't run one domain controller.",
    "ipa user-find before you create. They might already exist. Twice.",
    "Always backup before running ipa-restore. That's not a suggestion.",
  ],
  certs: [
    "Your cert is probably fine. Probably. Check it anyway.",
    "Self-signed certs: the duct tape of PKI. Works until it doesn't.",
    "Renew early, renew often. Don't be that person at 2AM on a holiday.",
    "SAN fields matter. So do expiry dates. So does your job.",
    "A cert expired in production today somewhere in the world. Don't let it be yours.",
    "openssl s_client is your best friend. Learn it.",
    "The CA chain matters. The whole chain. Yes, the intermediate too.",
    "Let's Encrypt is free. Expired certs are expensive. Do the math.",
    "Wildcard certs: convenient until you need to revoke one.",
    "If you're not monitoring cert expiry, you're just planning a surprise outage.",
  ],
  system: [
    "Uptime is a vanity metric — until the server crashes.",
    "df -h before you delete anything. Always df -h first.",
    "SELinux: Enforcing means it's working. Permissive means it's writing your audit.",
    "Check your disk space. Check it now. Now check /var/log.",
    "systemd said what? journalctl -xe has the full story.",
    "Load average high? top -c and figure out who the culprit is.",
    "That service that keeps restarting is trying to tell you something. Listen.",
    "FIPS mode: not just a toggle. Make sure your apps know about it too.",
    "OOM killer visited last night. Check the journal. It left notes.",
    "NTP sync drift above 1 second is Kerberos's cue to stop working.",
  ],
  kvm: [
    "VMs are like cats. They multiply when you're not looking.",
    "Snapshot before the upgrade. I cannot stress this enough.",
    "That VM has been 'temporarily' shut off for 6 months. It's permanent now.",
    "virsh list --all. Count them. Where did all these VMs come from?",
    "Autostart: set it, or deal with the aftermath after every reboot.",
    "Disk is cheap. Running out of it on a hypervisor is not.",
    "Live migration: impressive until your storage can't keep up.",
    "Nested virtualization: because one layer of complexity wasn't enough.",
    "That snapshot chain is 47 levels deep. Someone made choices.",
    "vCPU overcommit: fine at 2:1. Questionable at 8:1. Reckless at 16:1.",
  ],
  dnf: [
    "sudo dnf update — the answer to 42% of all problems.",
    "That package has a security update. From 3 months ago. Just saying.",
    "EPEL: for when the base repos just aren't enough.",
    "Air-gapped? Your repo mirror better be synced. When did you last sync?",
    "Kernel updates require a reboot. Schedule it. Don't just hope.",
    "dnf history undo: the safety net you didn't know you needed.",
    "Module streams: Rocky 9's way of saying 'pick a version and commit.'",
    "GPG key verification: don't skip it, even on your own mirror.",
    "dnf check-update first, dnf update second. Read what's changing.",
    "Automatic updates: great for patches, terrifying at 2AM on a Friday.",
  ],
  docker: [
    "Have you updated your base image? When? I'll wait.",
    "Containers are cattle, not pets. Stop naming them after family members.",
    "docker compose down && up -d — the container two-step.",
    "That exited container has been exited for 47 days. It's time.",
    "Port 8080 is always taken. By something you forgot you ran.",
    "Latest tag is not a version. It's a mystery box.",
    "Your container logs are in journalctl if you're using the journal driver.",
    "Rootless containers: because not everything needs to run as root.",
    "docker system prune -af — use responsibly. Very responsibly.",
    "Health checks in your compose file: not optional, they're a promise to your future self.",
  ],
  network: [
    "Ping works. The service doesn't. That's layer 7's problem now.",
    "Check the firewall. Then check DNS. Then check the firewall again.",
    "Latency is a symptom. Packet loss is a confession.",
    "TCP handshake succeeded: the most optimistic moment in networking.",
    "If ICMP is blocked, is the host even really there? Philosophically speaking.",
    "MTU mismatch: the silent killer of otherwise perfect connections.",
    "ss -tlnp — what's actually listening vs what you think is listening.",
    "Firewalld down doesn't mean no firewall. It means no managed firewall.",
    "VLAN misconfiguration: it's always on the switch port you didn't check.",
    "Spanning tree: still causing outages, still not getting enough blame.",
  ],
  logs: [
    "The logs told you this was coming. You just weren't reading them.",
    "grep is free. logrotate is not optional. Both save lives.",
    "Journal errors at 3AM are the system's way of saying 'we need to talk.'",
    "Auth failures in /var/log/secure: someone's having a rough night. Hopefully not you.",
    "A sysadmin who doesn't read logs is just someone who sits near servers.",
    "journalctl --since '1 hour ago' — start there, then expand.",
    "Log retention policy: have one. In writing. Before the audit.",
    "1000 auth failures from one IP is a brute force attempt. Block it.",
    "Your app logs to /tmp. You didn't set up logrotate. I'll see myself out.",
    "Quiet logs are either a good sign or a very bad sign. Check which.",
  ],
};

/* Tips shown after tool execution — keyed by exit code */
const RESULT_TIPS = {
  0: [
    "Clean exit. You've earned a coffee.",
    "All green. Now document what you just did.",
    "No errors. Enjoy it — it won't last.",
    "Success. Go take a victory lap around the server room.",
    "Everything is fine. This is fine.",
  ],
  1: [
    "Something went wrong. The logs probably know more than I do.",
    "Exit code 1. Time to read stderr carefully.",
    "Errors detected. Don't panic. Panic later.",
    "Well that's not ideal. Check the output above.",
    "The tool had thoughts. Not good ones. Read the output.",
  ],
  2: [
    "Warnings found. Not on fire, but warm. Worth a look.",
    "Exit 2 means something needs your attention. You're already on it.",
    "WARN threshold triggered. Your future self will thank you for checking.",
    "Yellow flags on the field. Review the results above.",
    "Not broken, but not happy either. Investigate.",
  ],
};

/* ─────────────────────────────────────────────────────────────────────
   THEME
───────────────────────────────────────────────────────────────────── */
const Theme = (() => {
  const STORAGE_KEY = 'lrn-theme';
  const html = document.documentElement;
  let current = 'dark';

  function apply(theme) {
    current = theme;
    html.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
    const icon  = document.getElementById('theme-icon');
    const label = document.getElementById('theme-label');
    if (icon)  icon.textContent  = theme === 'dark' ? '\u2600' : '\uD83C\uDF19'; // ☀ / 🌙
    if (label) label.textContent = theme === 'dark' ? 'Light' : 'Dark';
  }

  function init() {
    const saved = localStorage.getItem(STORAGE_KEY) || 'dark';
    apply(saved);
  }

  function toggle() {
    apply(current === 'dark' ? 'light' : 'dark');
  }

  return { init, toggle, current: () => current };
})();

/* ─────────────────────────────────────────────────────────────────────
   LRN MAN MASCOT
───────────────────────────────────────────────────────────────────── */
const LrnMan = (() => {
  const STORAGE_KEY  = 'lrn-man-visible';
  const AUTO_DELAY   = 3000;   // ms before first auto-show
  const AUTO_ROTATE  = 45000;  // ms between auto-tip rotations

  let visible    = true;   // mascot container visible
  let bubbleOpen = false;  // speech bubble shown
  let tipIndex   = 0;
  let rotateTimer = null;
  let categoryTips = [];

  /* Determine tip pool from current page */
  function buildTipPool() {
    const toolId = document.body.dataset.toolId || '';
    const prefix = toolId.split('-')[0] || '';
    const catPool = TIPS[prefix] || [];
    // Merge general + category-specific, shuffle category tips first
    categoryTips = [...catPool, ...TIPS.general];
    tipIndex = 0;
  }

  function currentTip() {
    return categoryTips[tipIndex % categoryTips.length];
  }

  function nextTip() {
    tipIndex = (tipIndex + 1) % categoryTips.length;
    document.getElementById('lrn-tip-text').textContent = currentTip();
  }

  function showBubble() {
    const bubble = document.getElementById('lrn-bubble');
    const tipEl  = document.getElementById('lrn-tip-text');
    if (!bubble || !tipEl) return;
    tipEl.textContent = currentTip();
    bubble.classList.remove('lrn-hidden');
    bubbleOpen = true;
    startRotation();
  }

  function hideBubble() {
    const bubble = document.getElementById('lrn-bubble');
    if (bubble) bubble.classList.add('lrn-hidden');
    bubbleOpen = false;
    stopRotation();
  }

  function toggleBubble() {
    bubbleOpen ? hideBubble() : showBubble();
  }

  function startRotation() {
    stopRotation();
    rotateTimer = setInterval(() => {
      tipIndex = (tipIndex + 1) % categoryTips.length;
      const el = document.getElementById('lrn-tip-text');
      if (el && bubbleOpen) el.textContent = currentTip();
    }, AUTO_ROTATE);
  }

  function stopRotation() {
    if (rotateTimer) { clearInterval(rotateTimer); rotateTimer = null; }
  }

  function showMascot() {
    const container = document.getElementById('lrn-man-container');
    if (container) container.classList.remove('hidden');
    visible = true;
    localStorage.setItem(STORAGE_KEY, '1');
    const label = document.getElementById('mascot-label');
    if (label) label.textContent = 'Guide: ON';
    const btn = document.getElementById('mascot-toggle');
    if (btn) btn.classList.add('active');
  }

  function hideMascot() {
    hideBubble();
    const container = document.getElementById('lrn-man-container');
    if (container) container.classList.add('hidden');
    visible = false;
    localStorage.setItem(STORAGE_KEY, '0');
    const label = document.getElementById('mascot-label');
    if (label) label.textContent = 'Guide: OFF';
    const btn = document.getElementById('mascot-toggle');
    if (btn) btn.classList.remove('active');
  }

  function toggleMascot() {
    visible ? hideMascot() : showMascot();
  }

  /* Called externally after a tool run completes */
  function commentOnResult(exitCode) {
    if (!visible) return;
    const pool = RESULT_TIPS[exitCode] || RESULT_TIPS[1];
    const msg  = pool[Math.floor(Math.random() * pool.length)];
    const tipEl = document.getElementById('lrn-tip-text');
    if (tipEl) tipEl.textContent = msg;
    if (!bubbleOpen) showBubble();
    stopRotation(); // don't auto-rotate away from result tip
    // Resume rotation after 12 seconds
    setTimeout(startRotation, 12000);
  }

  function init() {
    buildTipPool();

    // Restore visibility preference
    const savedVisible = localStorage.getItem(STORAGE_KEY);
    if (savedVisible === '0') {
      hideMascot();
    } else {
      showMascot();
      // Auto-show bubble after delay (only on first visit or dashboard)
      const page = document.body.dataset.page || '';
      if (page === 'index' || !page) {
        setTimeout(() => { if (visible) showBubble(); }, AUTO_DELAY);
      }
    }

    // Wire up clicks
    const img     = document.getElementById('lrn-man-img');
    const dismiss = document.getElementById('lrn-dismiss');
    const nextBtn = document.getElementById('lrn-next');

    if (img)     img.addEventListener('click', toggleBubble);
    if (dismiss) dismiss.addEventListener('click', hideBubble);
    if (nextBtn) nextBtn.addEventListener('click', nextTip);
  }

  return { init, toggleMascot, commentOnResult, showBubble, hideBubble };
})();

/* ─────────────────────────────────────────────────────────────────────
   MAIN INIT
───────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {

  // Apply saved theme immediately (before render)
  Theme.init();

  // Theme toggle button
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', Theme.toggle);

  // Mascot toggle button
  const mascotBtn = document.getElementById('mascot-toggle');
  if (mascotBtn) mascotBtn.addEventListener('click', LrnMan.toggleMascot);

  // Init mascot
  LrnMan.init();

  // Active nav highlight
  const path = window.location.pathname;
  document.querySelectorAll('.nav-tool, .nav-home').forEach(a => {
    if (a.getAttribute('href') === path) a.classList.add('active');
  });
});

/* Expose LrnMan globally so tool_run.html inline scripts can call it */
window.LrnMan = LrnMan;
