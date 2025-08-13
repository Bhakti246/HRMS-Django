/* HRMS — Single Page App (Vanilla JS) */
(function () {
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));

  const appEl = $("#app");
  const sidebar = $("#sidebar");
  const sidebarToggle = $("#sidebarToggle");
  const toastEl = $("#toast");
  const modalRoot = $("#modal-root");
  const globalSearch = $("#globalSearch");
  const toggleTheme = $("#toggleTheme");

  /* Theme toggle */
  const THEME_KEY = "hrms_theme";
  function applyTheme(theme) {
    if (theme === "light") {
      document.documentElement.style.setProperty("--bg", "#f6f7fb");
      document.documentElement.style.setProperty("--panel", "#ffffff");
      document.documentElement.style.setProperty("--muted", "#f0f2f8");
      document.documentElement.style.setProperty("--text", "#0b1220");
      document.documentElement.style.setProperty("--text-dim", "#4b5563");
      document.documentElement.style.setProperty("--border", "#e5e7eb");
      document.body.style.background = "#f6f7fb";
    } else {
      // default dark theme uses CSS vars
      document.documentElement.style.cssText = "";
    }
  }
  applyTheme(localStorage.getItem(THEME_KEY));
  toggleTheme.addEventListener("click", () => {
    const next = localStorage.getItem(THEME_KEY) === "light" ? "dark" : "light";
    if (next === "dark") localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, next);
    applyTheme(localStorage.getItem(THEME_KEY));
  });

  /* Sidebar toggle */
  sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("open");
  });

  /* Toast */
  let toastTimer = null;
  function showToast(message) {
    toastEl.textContent = message;
    toastEl.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2200);
  }

  /* Modal */
  function openModal(contentHtml, { title = "", onClose = null } = {}) {
    modalRoot.setAttribute("aria-hidden", "false");
    modalRoot.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true">
        <header>
          <strong>${title}</strong>
          <button class="icon-btn" id="modalClose" aria-label="Close">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M18.3 5.71L12 12.01 5.7 5.7 4.3 7.11l6.3 6.29-6.3 6.3 1.41 1.41 6.29-6.3 6.3 6.3 1.4-1.41-6.29-6.3 6.29-6.29z"/></svg>
          </button>
        </header>
        <div class="body">${contentHtml}</div>
      </div>`;
    $("#modalClose", modalRoot).addEventListener("click", closeModal);
    modalRoot.addEventListener("click", (e) => { if (e.target === modalRoot) closeModal(); });
    function closeModal() {
      modalRoot.setAttribute("aria-hidden", "true");
      modalRoot.innerHTML = "";
      if (onClose) onClose();
    }
    return closeModal;
  }

  /* Data Layer */
  const STORAGE_KEYS = {
    employees: "hrms_employees_v1",
    attendance: "hrms_attendance_v1",
    leave: "hrms_leave_v1",
    payroll: "hrms_payroll_v1",
    policies: "hrms_policies_v1",
    images: "hrms_images_v1",
  };

  const seedEmployees = [
    { id: "EMP-001", name: "Ananya Sharma", role: "HR Manager", dept: "HR", email: "ananya@company.com", phone: "+91 98765 43210", status: "Active", doj: "2022-05-10" },
    { id: "EMP-002", name: "Rohit Verma", role: "Software Engineer", dept: "Engineering", email: "rohit@company.com", phone: "+91 98111 11111", status: "Active", doj: "2023-02-01" },
    { id: "EMP-003", name: "Neha Gupta", role: "Data Analyst", dept: "Analytics", email: "neha@company.com", phone: "+91 98222 22222", status: "Inactive", doj: "2021-09-14" },
    { id: "EMP-004", name: "Arjun Mehta", role: "Product Manager", dept: "Product", email: "arjun@company.com", phone: "+91 98333 33333", status: "Active", doj: "2020-01-25" },
  ];

  const db = {
    getEmployees() {
      const raw = localStorage.getItem(STORAGE_KEYS.employees);
      return raw ? JSON.parse(raw) : seedEmployees.slice();
    },
    saveEmployees(list) {
      localStorage.setItem(STORAGE_KEYS.employees, JSON.stringify(list));
    },
    upsertEmployee(emp) {
      const list = this.getEmployees();
      const idx = list.findIndex((e) => e.id === emp.id);
      if (idx === -1) list.push(emp); else list[idx] = emp;
      this.saveEmployees(list);
    },
    deleteEmployee(id) {
      const list = this.getEmployees().filter((e) => e.id !== id);
      this.saveEmployees(list);
    },
    getPayroll(empId) {
      const raw = localStorage.getItem(STORAGE_KEYS.payroll);
      const payroll = raw ? JSON.parse(raw) : {};
      return payroll[empId] || { basic: 50000, hra: 20000, allowances: 5000, deductions: 6000 };
    },
    savePayroll(empId, data) {
      const raw = localStorage.getItem(STORAGE_KEYS.payroll);
      const payroll = raw ? JSON.parse(raw) : {};
      payroll[empId] = data;
      localStorage.setItem(STORAGE_KEYS.payroll, JSON.stringify(payroll));
    },
    getPolicies() {
      const raw = localStorage.getItem(STORAGE_KEYS.policies);
      return raw ? JSON.parse(raw) : [
        { id: "POL-001", title: "Employee Handbook", status: "pending", sentTo: "ananya@company.com", sentDate: "2024-01-15" },
        { id: "POL-002", title: "Code of Conduct", status: "signed", sentTo: "rohit@company.com", sentDate: "2024-01-10", signedDate: "2024-01-12" }
      ];
    },
    savePolicies(list) {
      localStorage.setItem(STORAGE_KEYS.policies, JSON.stringify(list));
    },
    getImage(empId) {
      const raw = localStorage.getItem(STORAGE_KEYS.images);
      const images = raw ? JSON.parse(raw) : {};
      return images[empId] || null;
    },
    saveImage(empId, imageData) {
      const raw = localStorage.getItem(STORAGE_KEYS.images);
      const images = raw ? JSON.parse(raw) : {};
      images[empId] = imageData;
      localStorage.setItem(STORAGE_KEYS.images, JSON.stringify(images));
    },
  };

  /* Router */
  const routes = {
    "#/dashboard": renderDashboard,
    "#/employees": renderEmployees,
    "#/attendance": renderAttendance,
    "#/leave": renderLeave,
    "#/payroll": renderPayroll,
    "#/recruitment": renderRecruitment,
    "#/performance": renderPerformance,
    "#/reports": renderReports,
    "#/settings": renderSettings,
  };

  function navigate() {
    const hash = location.hash || "#/dashboard";
    updateActiveNav(hash);
    const view = routes[hash] || renderNotFound;
    view();
    // close sidebar on mobile after navigation
    sidebar.classList.remove("open");
    appEl.focus();
  }
  window.addEventListener("hashchange", navigate);

  function updateActiveNav(hash) {
    $$(".nav-link").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === hash));
  }

  /* Global search: filters employee list when on Employees page */
  globalSearch.addEventListener("input", () => {
    if (location.hash !== "#/employees") return;
    renderEmployees(globalSearch.value.trim().toLowerCase());
  });

  /* Views */
  function renderDashboard() {
    const employees = db.getEmployees();
    const selectedId = localStorage.getItem('hrms_selected_employee') || employees[0]?.id;
    const person = employees.find(e => e.id === selectedId) || employees[0];
    if (person) localStorage.setItem('hrms_selected_employee', person.id);
    
    const payroll = db.getPayroll(person.id);
    const image = db.getImage(person.id);
    const policies = db.getPolicies();

    appEl.innerHTML = `
      <div class="profile-hero">
        <section class="card profile-card">
          <div class="profile-cover"></div>
          <div class="profile-main">
            ${image ? `<img src="${image}" class="profile-image" alt="${person?.name}" />` : `<div class="avatar-lg">${initials(person?.name || 'NA')}</div>`}
            <div class="profile-meta">
              <div class="profile-name">${person?.name || '—'}</div>
              <div class="profile-sub">${person?.role || ''} · ${person?.dept || ''}</div>
              <div class="chips">
                <span class="chip">ID: ${person?.id || ''}</span>
                <span class="chip">Status: ${person?.status || ''}</span>
                <span class="chip">DOJ: ${person?.doj || ''}</span>
              </div>
            </div>
            <div class="actions">
              <select id="empSwitcher" class="emp-switcher">
                ${employees.map(e=>`<option value="${e.id}" ${e.id===person.id?'selected':''}>${e.name}</option>`).join('')}
              </select>
              <button class="btn" id="editProfile">Edit</button>
              <button class="btn primary" id="emailProfile">Email</button>
            </div>
          </div>
        </section>

        <section class="card span-3">
          <div class="mini-header"><div class="mini-avatar">📷</div><div><div class="mini-title">Profile Photo</div><div class="muted">Upload image</div></div></div>
          <div class="divider"></div>
          <div id="uploadArea" class="upload-area">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M19 7v2.99s-1.99.01-2 0V7h-3s.01-1.99 0-2h3V2h2v3h3v2h-3zm-3 4V8h-3V5H5c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-8h-3zM5 19l3-4 2 3 3-4 4 5H5z"/></svg>
            <div>Click or drag to upload</div>
            <input type="file" id="imageUpload" accept="image/*" style="display:none" />
          </div>
        </section>

        <section class="card span-3">
          <div class="mini-header"><div class="mini-avatar">@</div><div><div class="mini-title">Contact</div><div class="muted">Reach out details</div></div></div>
          <div class="divider"></div>
          <div class="grid" style="grid-template-columns:repeat(12,1fr);gap:8px">
            <div class="field" style="grid-column:span 12"><label>Email</label><div>${person?.email || '—'}</div></div>
            <div class="field" style="grid-column:span 12"><label>Phone</label><div>${person?.phone || '—'}</div></div>
          </div>
        </section>
        <section class="card span-3">
          <div class="mini-header"><div class="mini-avatar">🏁</div><div><div class="mini-title">Employment</div><div class="muted">Basics</div></div></div>
          <div class="divider"></div>
          <div class="grid" style="grid-template-columns:repeat(12,1fr);gap:8px">
            <div class="field" style="grid-column:span 12"><label>Department</label><div>${person?.dept || '—'}</div></div>
            <div class="field" style="grid-column:span 12"><label>Role</label><div>${person?.role || '—'}</div></div>
            <div class="field" style="grid-column:span 12"><label>Status</label><div><span class="badge ${person?.status==='Active'?'success':'danger'}">${person?.status || '—'}</span></div></div>
          </div>
        </section>
        <section class="card span-3">
          <div class="mini-header"><div class="mini-avatar">₹</div><div><div class="mini-title">Payroll</div><div class="muted">Click to edit</div></div></div>
          <div class="divider"></div>
          <div class="metric"><span class="value">₹${payroll.basic + payroll.hra + payroll.allowances - payroll.deductions}</span><span class="sub">net</span></div>
          <div class="chips">
            <span class="chip">Basic ₹${payroll.basic.toLocaleString()}</span>
            <span class="chip">HRA ₹${payroll.hra.toLocaleString()}</span>
          </div>
          <button class="btn" id="editPayroll" style="margin-top:8px;width:100%">Edit Payroll</button>
        </section>

        <section class="card span-6">
          <div class="mini-header"><div class="mini-avatar">📊</div><div><div class="mini-title">Performance Metrics</div><div class="muted">This month</div></div></div>
          <div class="divider"></div>
          <div class="performance-grid">
            <div><div style="font-size:12px;margin-bottom:4px">Productivity</div><div class="perf-bar"><div class="perf-fill" style="width:85%"></div></div></div>
            <div><div style="font-size:12px;margin-bottom:4px">Quality</div><div class="perf-bar"><div class="perf-fill" style="width:92%"></div></div></div>
            <div><div style="font-size:12px;margin-bottom:4px">Attendance</div><div class="perf-bar"><div class="perf-fill" style="width:78%"></div></div></div>
            <div><div style="font-size:12px;margin-bottom:4px">Teamwork</div><div class="perf-bar"><div class="perf-fill" style="width:88%"></div></div></div>
            <div><div style="font-size:12px;margin-bottom:4px">Initiative</div><div class="perf-bar"><div class="perf-fill" style="width:95%"></div></div></div>
            <div><div style="font-size:12px;margin-bottom:4px">Learning</div><div class="perf-bar"><div class="perf-fill" style="width:82%"></div></div></div>
          </div>
        </section>

        <section class="card span-6">
          <div class="mini-header"><div class="mini-avatar">📋</div><div><div class="mini-title">HR Policies</div><div class="muted">Document signing</div></div></div>
          <div class="divider"></div>
          ${policies.map(p => `
            <div class="policy-card">
              <div class="policy-header">
                <div>
                  <div style="font-weight:600">${p.title}</div>
                  <div class="muted" style="font-size:12px">Sent to ${p.sentTo} on ${p.sentDate}</div>
                </div>
                <span class="policy-status ${p.status}">${p.status}</span>
              </div>
              ${p.signedDate ? `<div class="muted" style="font-size:12px">Signed on ${p.signedDate}</div>` : ''}
            </div>
          `).join('')}
          <button class="btn primary" id="sendPolicy" style="margin-top:8px;width:100%">Send New Policy</button>
        </section>

        <section class="card span-12">
          <h3>Quick actions</h3>
          <div class="divider"></div>
          <div class="toolbar">
            <div class="group">
              <button class="btn" onclick="location.hash='#/attendance'">Attendance</button>
              <button class="btn" onclick="location.hash='#/leave'">Request Leave</button>
              <button class="btn" onclick="location.hash='#/performance'">Performance</button>
              <button class="btn" onclick="location.hash='#/employees'">Directory</button>
            </div>
            <div class="group">
              <button class="btn success" id="saveProfile">Save Profile</button>
            </div>
          </div>
        </section>
      </div>
    `;

    $("#empSwitcher").addEventListener('change', (e) => {
      localStorage.setItem('hrms_selected_employee', e.target.value);
      renderDashboard();
    });
    $("#editProfile").addEventListener('click', () => openEmployeeForm(person.id));
    $("#emailProfile").addEventListener('click', () => showToast('Opening mail client…'));
    $("#saveProfile").addEventListener('click', () => showToast('Profile saved'));
    $("#editPayroll").addEventListener('click', () => openPayrollForm(person.id));
    $("#sendPolicy").addEventListener('click', () => openPolicyForm(person.id));
    
    // Image upload
    const uploadArea = $("#uploadArea");
    const imageUpload = $("#imageUpload");
    
    uploadArea.addEventListener('click', () => imageUpload.click());
    uploadArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadArea.classList.add('dragover');
    });
    uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
    uploadArea.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadArea.classList.remove('dragover');
      const file = e.dataTransfer.files[0];
      if (file && file.type.startsWith('image/')) {
        handleImageUpload(file);
      }
    });
    imageUpload.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) handleImageUpload(file);
    });
  }

  function renderEmployees(filterText = (globalSearch.value || "").toLowerCase()) {
    const employees = db.getEmployees().filter((e) => {
      const blob = `${e.id} ${e.name} ${e.role} ${e.dept} ${e.email} ${e.phone} ${e.status}`.toLowerCase();
      return blob.includes(filterText);
    });

    appEl.innerHTML = `
      <div class="toolbar">
        <div class="group">
          <input id="empSearch" class="input" placeholder="Search employees" value="${filterText}" />
          <select id="empDept" class="select">
            <option value="">All Departments</option>
            ${Array.from(new Set(db.getEmployees().map(e=>e.dept))).map(d=>`<option value="${d}">${d}</option>`).join("")}
          </select>
          <select id="empStatus" class="select">
            <option value="">All Status</option>
            <option value="Active">Active</option>
            <option value="Inactive">Inactive</option>
          </select>
        </div>
        <div class="group">
          <button class="btn" id="exportCsv">Export CSV</button>
          <button class="btn primary" id="addEmployee">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M19 11H13V5h-2v6H5v2h6v6h2v-6h6z"/></svg>
            Add Employee
          </button>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Role</th>
              <th>Department</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Status</th>
              <th>DOJ</th>
              <th style="width:120px">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${employees.map((e)=>`
              <tr>
                <td>${e.id}</td>
                <td>${e.name}</td>
                <td>${e.role}</td>
                <td>${e.dept}</td>
                <td>${e.email}</td>
                <td>${e.phone}</td>
                <td><span class="badge ${e.status === 'Active' ? 'success' : 'danger'}">${e.status}</span></td>
                <td>${e.doj}</td>
                <td>
                  <div style="display:flex;gap:6px">
                    <button class="btn" data-edit="${e.id}">Edit</button>
                    <button class="btn danger" data-del="${e.id}">Delete</button>
                  </div>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;

    $("#empSearch").addEventListener("input", (e) => renderEmployees(e.target.value.toLowerCase()));
    $("#empDept").addEventListener("change", (e) => {
      const val = e.target.value;
      const q = (globalSearch.value || "").toLowerCase();
      const emps = db.getEmployees().filter(emp => (!val || emp.dept === val));
      const filtered = emps.filter((emp) => `${emp.id} ${emp.name} ${emp.role} ${emp.dept} ${emp.email} ${emp.phone} ${emp.status}`.toLowerCase().includes(q));
      renderEmployeesFromList(filtered);
    });
    $("#empStatus").addEventListener("change", (e) => {
      const val = e.target.value;
      const q = (globalSearch.value || "").toLowerCase();
      const emps = db.getEmployees().filter(emp => (!val || emp.status === val));
      const filtered = emps.filter((emp) => `${emp.id} ${emp.name} ${emp.role} ${emp.dept} ${emp.email} ${emp.phone} ${emp.status}`.toLowerCase().includes(q));
      renderEmployeesFromList(filtered);
    });
    $("#exportCsv").addEventListener("click", () => exportEmployeesCsv(db.getEmployees()));
    $("#addEmployee").addEventListener("click", () => openEmployeeForm());

    $$('[data-edit]').forEach((btn) => btn.addEventListener('click', () => openEmployeeForm(btn.getAttribute('data-edit'))));
    $$('[data-del]').forEach((btn) => btn.addEventListener('click', () => deleteEmployee(btn.getAttribute('data-del'))));

    function renderEmployeesFromList(list) {
      // Only update tbody for speed
      const tbody = appEl.querySelector('tbody');
      tbody.innerHTML = list.map((e)=>`
        <tr>
          <td>${e.id}</td>
          <td>${e.name}</td>
          <td>${e.role}</td>
          <td>${e.dept}</td>
          <td>${e.email}</td>
          <td>${e.phone}</td>
          <td><span class="badge ${e.status === 'Active' ? 'success' : 'danger'}">${e.status}</span></td>
          <td>${e.doj}</td>
          <td>
            <div style="display:flex;gap:6px">
              <button class="btn" data-edit="${e.id}">Edit</button>
              <button class="btn danger" data-del="${e.id}">Delete</button>
            </div>
          </td>
        </tr>
      `).join('');

      $$('[data-edit]').forEach((btn) => btn.addEventListener('click', () => openEmployeeForm(btn.getAttribute('data-edit'))));
      $$('[data-del]').forEach((btn) => btn.addEventListener('click', () => deleteEmployee(btn.getAttribute('data-del'))));
    }
  }

  function exportEmployeesCsv(list) {
    const headers = ["ID","Name","Role","Department","Email","Phone","Status","DOJ"];
    const rows = list.map(e => [e.id, e.name, e.role, e.dept, e.email, e.phone, e.status, e.doj]);
    const csv = [headers, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g,'""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'employees.csv'; a.click();
    URL.revokeObjectURL(url);
    showToast("Exported employees.csv");
  }

  function openEmployeeForm(editId = null) {
    const edit = editId ? db.getEmployees().find(e => e.id === editId) : null;
    const close = openModal(`
      <form id="empForm">
        <div class="grid">
          <div class="field" style="grid-column:span 6">
            <label>Employee ID</label>
            <input class="input" name="id" required ${edit ? 'readonly' : ''} value="${edit?.id || generateEmpId()}" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Department</label>
            <input class="input" name="dept" required value="${edit?.dept || ''}" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Full Name</label>
            <input class="input" name="name" required value="${edit?.name || ''}" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Role</label>
            <input class="input" name="role" required value="${edit?.role || ''}" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Email</label>
            <input class="input" name="email" type="email" required value="${edit?.email || ''}" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Phone</label>
            <input class="input" name="phone" required value="${edit?.phone || ''}" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Status</label>
            <select class="select" name="status">
              <option ${!edit || edit.status === 'Active' ? 'selected' : ''}>Active</option>
              <option ${edit && edit.status === 'Inactive' ? 'selected' : ''}>Inactive</option>
            </select>
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Date of Joining</label>
            <input class="input" name="doj" type="date" required value="${edit?.doj || today()}" />
          </div>
        </div>
        <div class="toolbar" style="margin-top:12px">
          <span class="muted">${edit ? 'Edit employee and save changes' : 'Add a new employee to HRMS'}</span>
          <div class="group">
            <button type="button" class="btn" id="cancelEmp">Cancel</button>
            <button type="submit" class="btn success">Save</button>
          </div>
        </div>
      </form>
    `, { title: edit ? `Edit Employee — ${edit.name}` : "Add Employee" });

    $("#cancelEmp", modalRoot).addEventListener("click", () => close());
    $("#empForm", modalRoot).addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const emp = Object.fromEntries(fd.entries());
      db.upsertEmployee(emp);
      showToast(edit ? "Employee updated" : "Employee added");
      close();
      renderEmployees();
    });
  }

  function deleteEmployee(id) {
    if (!confirm("Delete this employee?")) return;
    db.deleteEmployee(id);
    showToast("Employee deleted");
    renderEmployees();
  }

  function openPayrollForm(empId) {
    const person = db.getEmployees().find(e => e.id === empId);
    const payroll = db.getPayroll(empId);
    const close = openModal(`
      <form id="payrollForm">
        <div class="grid">
          <div class="field" style="grid-column:span 6">
            <label>Basic Salary</label>
            <input class="input" name="basic" type="number" required value="${payroll.basic}" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>HRA</label>
            <input class="input" name="hra" type="number" required value="${payroll.hra}" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Allowances</label>
            <input class="input" name="allowances" type="number" required value="${payroll.allowances}" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Deductions</label>
            <input class="input" name="deductions" type="number" required value="${payroll.deductions}" />
          </div>
        </div>
        <div class="divider"></div>
        <div style="text-align:center;padding:12px;background:var(--muted);border-radius:8px">
          <div class="muted">Net Pay</div>
          <div style="font-size:24px;font-weight:700">₹${payroll.basic + payroll.hra + payroll.allowances - payroll.deductions}</div>
        </div>
        <div class="toolbar" style="margin-top:12px">
          <span class="muted">Edit payroll for ${person?.name}</span>
          <div class="group">
            <button type="button" class="btn" id="cancelPayroll">Cancel</button>
            <button type="submit" class="btn success">Save</button>
          </div>
        </div>
      </form>
    `, { title: `Edit Payroll — ${person?.name}` });

    $("#cancelPayroll", modalRoot).addEventListener("click", () => close());
    $("#payrollForm", modalRoot).addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const data = {
        basic: parseInt(fd.get('basic')),
        hra: parseInt(fd.get('hra')),
        allowances: parseInt(fd.get('allowances')),
        deductions: parseInt(fd.get('deductions'))
      };
      db.savePayroll(empId, data);
      showToast("Payroll updated");
      close();
      renderDashboard();
    });
  }

  function openPolicyForm(empId) {
    const person = db.getEmployees().find(e => e.id === empId);
    const close = openModal(`
      <form id="policyForm">
        <div class="grid">
          <div class="field" style="grid-column:span 6">
            <label>Policy Title</label>
            <input class="input" name="title" required placeholder="e.g., Employee Handbook" />
          </div>
          <div class="field" style="grid-column:span 6">
            <label>Send To</label>
            <input class="input" name="email" type="email" required value="${person?.email || ''}" />
          </div>
          <div class="field" style="grid-column:span 12">
            <label>Policy Type</label>
            <select class="select" name="type">
              <option>Employee Handbook</option>
              <option>Code of Conduct</option>
              <option>Non-Disclosure Agreement</option>
              <option>Employment Contract</option>
              <option>Leave Policy</option>
            </select>
          </div>
          <div class="field" style="grid-column:span 12">
            <label>Message (Optional)</label>
            <textarea class="input" name="message" rows="3" placeholder="Add a personal message..."></textarea>
          </div>
        </div>
        <div class="toolbar" style="margin-top:12px">
          <span class="muted">Send policy document to ${person?.name}</span>
          <div class="group">
            <button type="button" class="btn" id="cancelPolicy">Cancel</button>
            <button type="submit" class="btn success">Send Policy</button>
          </div>
        </div>
      </form>
    `, { title: `Send Policy — ${person?.name}` });

    $("#cancelPolicy", modalRoot).addEventListener("click", () => close());
    $("#policyForm", modalRoot).addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const policies = db.getPolicies();
      const newPolicy = {
        id: `POL-${Date.now()}`,
        title: fd.get('title'),
        status: 'pending',
        sentTo: fd.get('email'),
        sentDate: today(),
        type: fd.get('type'),
        message: fd.get('message')
      };
      policies.push(newPolicy);
      db.savePolicies(policies);
      showToast("Policy sent for signing");
      close();
      renderDashboard();
    });
  }

  function handleImageUpload(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const employees = db.getEmployees();
      const selectedId = localStorage.getItem('hrms_selected_employee') || employees[0]?.id;
      db.saveImage(selectedId, e.target.result);
      showToast("Profile photo uploaded");
      renderDashboard();
    };
    reader.readAsDataURL(file);
  }

  function renderAttendance() {
    const employees = db.getEmployees();
    const selectedId = localStorage.getItem('hrms_selected_employee') || employees[0]?.id;
    const person = employees.find(e => e.id === selectedId) || employees[0];
    appEl.innerHTML = `
      <div class="toolbar">
        <div class="group">
          <input class="input" placeholder="Search by name or ID" value="${person?.name || ''}" />
          <select class="select"><option>Today</option><option>This Week</option><option>This Month</option></select>
        </div>
        <div class="group">
          <button class="btn">Sync</button>
          <button class="btn primary">Mark In/Out</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Employee</th><th>Date</th><th>In</th><th>Out</th><th>Status</th></tr></thead>
          <tbody>
            <tr><td>${person?.name || '—'}</td><td>${today()}</td><td>09:56</td><td>—</td><td><span class="badge warning">In Office</span></td></tr>
          </tbody>
        </table>
      </div>
    `;
  }

  function renderLeave() {
    const employees = db.getEmployees();
    const selectedId = localStorage.getItem('hrms_selected_employee') || employees[0]?.id;
    const person = employees.find(e => e.id === selectedId) || employees[0];
    appEl.innerHTML = `
      <div class="toolbar">
        <div class="group">
          <button class="btn primary" id="requestLeave">Request Leave</button>
        </div>
        <div class="group">
          <select class="select"><option>All</option><option>Pending</option><option>Approved</option><option>Rejected</option></select>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Employee</th><th>Type</th><th>Dates</th><th>Days</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            <tr><td>${person?.name || '—'}</td><td>Casual</td><td>10–11 ${monName()}</td><td>2</td><td><span class="badge warning">Pending</span></td><td><button class="btn success">Approve</button></td></tr>
          </tbody>
        </table>
      </div>
    `;

    $("#requestLeave")?.addEventListener("click", () => openModal(`
      <div class="grid">
        <div class="field"><label>Employee</label><input class="input" value="${person?.name || ''}"/></div>
        <div class="field"><label>Type</label><select class="select"><option>Casual</option><option>Sick</option><option>Privilege</option></select></div>
        <div class="field"><label>From</label><input class="input" type="date" value="${today()}"/></div>
        <div class="field"><label>To</label><input class="input" type="date" value="${today()}"/></div>
        <div class="field"><label>Reason</label><input class="input" placeholder="Optional"/></div>
      </div>
      <div class="toolbar"><span class="muted">Submit leave request for approval</span><div class="group"><button class="btn">Cancel</button><button class="btn success">Submit</button></div></div>
    `, { title: "Request Leave" }));
  }

  function renderPayroll() {
    const employees = db.getEmployees();
    const selectedId = localStorage.getItem('hrms_selected_employee') || employees[0]?.id;
    const person = employees.find(e => e.id === selectedId) || employees[0];
    appEl.innerHTML = `
      <div class="cards">
        <section class="card span-6"><h3>Payroll Status — ${person?.name || '—'}</h3><div class="divider"></div><p class="muted">Draft for May ready.</p><div class="space"></div><button class="btn primary">Run Payroll</button></section>
        <section class="card span-6"><h3>Deductions & Earnings</h3><div class="divider"></div><p class="muted">Basic, HRA, Allowances for selected employee.</p><div class="space"></div><div class="chips"><span class="chip">Basic 50%</span><span class="chip">HRA 40%</span><span class="chip">Allow 10%</span></div></section>
      </div>
      <div class="space"></div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Employee</th><th>Basic</th><th>HRA</th><th>Allowances</th><th>Deductions</th><th>Net Pay</th></tr></thead>
          <tbody>
            <tr><td>${person?.name || '—'}</td><td>₹${baseFor(person)}</td><td>₹${hraFor(person)}</td><td>₹${allowFor(person)}</td><td>₹${deductFor(person)}</td><td>₹${salaryFor(person)}</td></tr>
          </tbody>
        </table>
      </div>
    `;
  }

  function renderRecruitment() {
    appEl.innerHTML = `
      <div class="toolbar">
        <div class="group"><button class="btn primary">New Job</button></div>
        <div class="group"><input class="input" placeholder="Search jobs/candidates"/></div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Job Title</th><th>Department</th><th>Openings</th><th>Stage</th><th>Applicants</th></tr></thead>
          <tbody>
            <tr><td>Frontend Engineer</td><td>Engineering</td><td>2</td><td><span class="badge warning">Screening</span></td><td>34</td></tr>
            <tr><td>HR Executive</td><td>HR</td><td>1</td><td><span class="badge success">Offer</span></td><td>12</td></tr>
          </tbody>
        </table>
      </div>
    `;
  }

  function renderPerformance() {
    const employees = db.getEmployees();
    const selectedId = localStorage.getItem('hrms_selected_employee') || employees[0]?.id;
    const person = employees.find(e => e.id === selectedId) || employees[0];
    appEl.innerHTML = `
      <div class="cards">
        <section class="card span-4"><h3>${person?.name || '—'} — Reviews Due</h3><div class="metric"><span class="value">1</span><span class="sub">this month</span></div></section>
        <section class="card span-4"><h3>Goals Tracked</h3><div class="metric"><span class="value">42</span><span class="sub">active</span></div></section>
        <section class="card span-4"><h3>Pulse Score</h3><div class="metric"><span class="value">7.9</span><span class="sub">/ 10</span></div></section>
        <section class="card span-12"><h3>OKR Snapshot</h3><div class="divider"></div><p class="muted">Individual and team OKRs overview (demo).</p></section>
      </div>
    `;
  }

  function renderReports() {
    const employees = db.getEmployees();
    const selectedId = localStorage.getItem('hrms_selected_employee') || employees[0]?.id;
    const person = employees.find(e => e.id === selectedId) || employees[0];
    appEl.innerHTML = `
      <div class="toolbar">
        <div class="group">
          <select class="select">
            <option>Headcount</option>
            <option>Attrition</option>
            <option>Attendance</option>
            <option>Payroll</option>
          </select>
          <button class="btn">Generate</button>
        </div>
        <div class="group">
          <button class="btn">Download PDF</button>
        </div>
      </div>
      <div class="card"><h3>Report — Focus: ${person?.name || '—'}</h3><div class="divider"></div><p class="muted">Use filters above to generate detailed reports for the selected employee or overall.</p></div>
    `;
  }

  function renderSettings() {
    const employees = db.getEmployees();
    const selectedId = localStorage.getItem('hrms_selected_employee') || employees[0]?.id;
    const person = employees.find(e => e.id === selectedId) || employees[0];
    appEl.innerHTML = `
      <div class="cards">
        <section class="card span-6"><h3>Company Profile</h3><div class="divider"></div><div class="grid"><div class="field"><label>Name</label><input class="input" value="Acme Pvt Ltd"/></div><div class="field"><label>Timezone</label><input class="input" value="IST (UTC+5:30)"/></div></div><div class="space"></div><button class="btn success">Save</button></section>
        <section class="card span-6"><h3>Leave Policy</h3><div class="divider"></div><p class="muted">Configure carry-forward, accruals, and types.</p><div class="space"></div><button class="btn">Edit Policy</button></section>
        <section class="card span-6"><h3>Attendance — ${person?.name || '—'}</h3><div class="divider"></div><p class="muted">Personalized attendance preferences (demo).</p><div class="space"></div><button class="btn">Configure</button></section>
        <section class="card span-6"><h3>Integrations</h3><div class="divider"></div><p class="muted">Connect Slack, Google, Payroll banks.</p><div class="space"></div><button class="btn">Manage</button></section>
      </div>
    `;
  }

  function renderNotFound() {
    appEl.innerHTML = `<div class="card"><h3>Not Found</h3><p class="muted">The page you are looking for does not exist.</p></div>`;
  }

  /* Helpers */
  function today() { const d = new Date(); return d.toISOString().slice(0,10); }
  function monName() { return new Date().toLocaleString(undefined, { month: 'short' }); }
  function generateEmpId() {
    const n = Math.floor(100 + Math.random() * 900);
    const ts = Date.now().toString().slice(-3);
    return `EMP-${n}${ts}`;
  }
  function initials(name) {
    return (name || 'NA').split(' ').map(s=>s[0]).join('').slice(0,2).toUpperCase();
  }
  function baseFor(p){ return p ? 50000 : 0; }
  function hraFor(p){ return p ? Math.round(baseFor(p)*0.4) : 0; }
  function allowFor(p){ return p ? Math.round(baseFor(p)*0.1) : 0; }
  function deductFor(p){ return p ? Math.round(baseFor(p)*0.12) : 0; }
  function salaryFor(p){ return p ? baseFor(p)+hraFor(p)+allowFor(p)-deductFor(p) : 0; }

  // initial render
  navigate();
})();


