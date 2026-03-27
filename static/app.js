document.addEventListener('DOMContentLoaded', () => {
    // --- State ---
    let meetings = [];
    let currentStep = 1;
    let meetingMode = 'single'; // 'single' or 'group'
    let selectedParticipants = [];
    let allUsers = [];

    // --- Elements ---
    const totalMeetingsEl = document.getElementById('totalMeetings');
    const upcomingMeetingsEl = document.getElementById('upcomingMeetings');
    const acceptedMeetingsEl = document.getElementById('acceptedMeetings');
    const declinedMeetingsEl = document.getElementById('declinedMeetings');
    const meetingsBody = document.getElementById('meetingsBody');
    const sidebarNav = document.getElementById('sidebarNav');
    const sections = document.querySelectorAll('.section');
    const navLinks = document.querySelectorAll('.nav-link');
    const usersBody = document.getElementById('usersBody');

    // Modals
    const createModal = document.getElementById('createModal');
    const detailsModal = document.getElementById('detailsModal');
    const userModal = document.getElementById('userModal');

    // Wizard Elements
    const wizardSteps = document.querySelectorAll('.wizard-step');
    const wizardBackBtn = document.getElementById('wizardBackBtn');
    const wizardNextBtn = document.getElementById('wizardNextBtn');
    const wizardSubmitBtn = document.getElementById('wizardSubmitBtn');
    const singleUserList = document.getElementById('singleUserList');
    const groupUserList = document.getElementById('groupUserList');
    
    // Form Fields
    const meetTitle = document.getElementById('meetTitle');
    const meetDate = document.getElementById('meetDate');
    const meetAgenda = document.getElementById('meetAgenda');
    
    // Custom Time Picker
    const timeHour = document.getElementById('timeHour');
    const timeMinute = document.getElementById('timeMinute');
    const timeAmpm = document.getElementById('timeAmpm');
    
    // Custom Delivery Picker
    const delayDate = document.getElementById('delayDate');
    const delayHour = document.getElementById('delayHour');
    const delayMinute = document.getElementById('delayMinute');
    const delayAmpm = document.getElementById('delayAmpm');

    // Buttons
    const openModalBtn = document.getElementById('openModalBtn');
    const openUserModalBtn = document.getElementById('openUserModalBtn');
    const saveUserBtn = document.getElementById('saveUserBtn');

    // UI Results
    const creationResult = document.getElementById('creationResult');
    const userResult = document.getElementById('userResult');
    const userBtnText = document.getElementById('userBtnText');

    // --- Initialization ---
    initTimeDropdowns();
    fetchDashboardData();
    fetchUsers();
    initNotifications();

    // --- Functions ---

    function initTimeDropdowns() {
        for (let i = 1; i <= 12; i++) {
            const opt = document.createElement('option');
            opt.value = i; opt.textContent = i.toString().padStart(2, '0');
            timeHour.appendChild(opt);
            
            const opt2 = document.createElement('option');
            opt2.value = i; opt2.textContent = i.toString().padStart(2, '0');
            delayHour.appendChild(opt2);
        }
        for (let i = 0; i < 60; i += 5) {
            const opt = document.createElement('option');
            opt.value = i; opt.textContent = i.toString().padStart(2, '0');
            timeMinute.appendChild(opt);
            
            const opt2 = document.createElement('option');
            opt2.value = i; opt2.textContent = i.toString().padStart(2, '0');
            delayMinute.appendChild(opt2);
        }
    }

    // --- Event Listeners ---
    sidebarNav.onclick = (e) => {
        const link = e.target.closest('.nav-link');
        if (!link) return;
        e.preventDefault();
        const target = link.getAttribute('data-target');
        navLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        sections.forEach(s => {
            s.classList.remove('active');
            if (s.id === target + 'Section') s.classList.add('active');
        });
        if (target === 'dashboard') fetchDashboardData();
        if (target === 'users') fetchUsers();
    };

    openModalBtn.onclick = () => {
        resetWizard();
        createModal.style.display = 'flex';
    };
    
    openUserModalBtn.onclick = () => userModal.style.display = 'flex';
    
    document.querySelectorAll('.close, .close-modal').forEach(btn => {
        btn.onclick = () => {
            createModal.style.display = 'none';
            detailsModal.style.display = 'none';
            userModal.style.display = 'none';
            creationResult.classList.add('hidden');
            userResult.classList.add('hidden');
        };
    });

    window.onclick = (event) => {
        // Disabled backdrop-click for createModal to prevent accidental closure on mobile
        // if (event.target == createModal) createModal.style.display = 'none';
        if (event.target == detailsModal) detailsModal.style.display = 'none';
        if (event.target == userModal) userModal.style.display = 'none';
    };

    // Wizard Logic
    document.getElementById('modeSingle').onclick = () => { meetingMode = 'single'; showStep(2); };
    document.getElementById('modeGroup').onclick = () => { meetingMode = 'group'; showStep(2); };

    // Single User Search
    const singleUserSearch = document.getElementById('singleUserSearch');
    singleUserSearch.oninput = () => renderParticipantSelection(singleUserSearch.value.trim().toLowerCase());

    wizardBackBtn.onclick = () => showStep(currentStep - 1);
    wizardNextBtn.onclick = () => {
        if (currentStep === 2) {
            if (selectedParticipants.length === 0) {
                alert('Please select at least one participant.');
                return;
            }
        }
        showStep(currentStep + 1);
    };
    wizardSubmitBtn.onclick = handleCreateMeeting;

    saveUserBtn.onclick = handleAddUser;

    // Search filter
    const searchInput = document.querySelector('.search-bar input');
    if (searchInput) {
        searchInput.oninput = (e) => {
            const query = e.target.value.toLowerCase();
            const rows = meetingsBody.querySelectorAll('tr');
            rows.forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
        };
    }

    // --- Core Functions ---

    function resetWizard() {
        currentStep = 1;
        selectedParticipants = [];
        meetTitle.value = '';
        meetDate.value = '';
        meetAgenda.value = '';
        // Reset custom time
        timeHour.selectedIndex = 0;
        timeMinute.selectedIndex = 0;
        timeAmpm.value = 'AM';
        
        document.getElementById('emailDeliveryMode').value = 'instant';
        document.getElementById('customDeliveryTime').classList.add('hidden');
        delayDate.value = '';
        delayHour.selectedIndex = 0;
        delayMinute.selectedIndex = 0;
        delayAmpm.value = 'AM';
        
        creationResult.classList.add('hidden');
        
        const today = new Date().toISOString().split('T')[0];
        meetDate.setAttribute('min', today);
        delayDate.setAttribute('min', today);
        
        showStep(1);
    }

    function showStep(step) {
        currentStep = step;
        wizardSteps.forEach((s, i) => s.classList.toggle('active', i === step - 1));
        
        wizardBackBtn.style.display = step > 1 ? 'block' : 'none';
        
        if (step === 1) {
            wizardNextBtn.style.display = 'none';
            wizardSubmitBtn.style.display = 'none';
        } else if (step === 2) {
            wizardNextBtn.style.display = (meetingMode === 'group') ? 'block' : 'none';
            wizardSubmitBtn.style.display = 'none';
            renderParticipantSelection();
        } else if (step === 3) {
            wizardNextBtn.style.display = 'none';
            wizardSubmitBtn.style.display = 'block';
        }
    }

    function renderParticipantSelection(query = '') {
        if (meetingMode === 'single') {
            document.getElementById('selectionSingle').classList.remove('hidden');
            document.getElementById('selectionGroup').classList.add('hidden');
            singleUserList.innerHTML = '';
            
            const filtered = allUsers.filter(u => 
                u.name.toLowerCase().includes(query) || u.email.toLowerCase().includes(query)
            );

            if (query && filtered.length > 0) {
                filtered.forEach(u => {
                    const div = document.createElement('div');
                    div.className = 'user-select-item';
                    div.innerHTML = `<span><strong>${u.name}</strong> (${u.email})</span>`;
                    div.onclick = () => {
                        selectedParticipants = [u];
                        showStep(3);
                    };
                    singleUserList.appendChild(div);
                });
            } else if (query) {
                singleUserList.innerHTML = '<p class="modal-hint">No matches found.</p>';
            } else {
                singleUserList.innerHTML = '<p class="modal-hint">Start typing to find a person...</p>';
            }
        } else {
            document.getElementById('selectionSingle').classList.add('hidden');
            document.getElementById('selectionGroup').classList.remove('hidden');
            groupUserList.innerHTML = '';
            allUsers.forEach(u => {
                const div = document.createElement('div');
                div.className = 'user-check-item';
                div.innerHTML = `
                    <input type="checkbox" id="user_${u.email}" value="${u.email}" 
                           ${selectedParticipants.find(p => p.email === u.email) ? 'checked' : ''}>
                    <label for="user_${u.email}"><strong>${u.name}</strong> (${u.email})</label>
                `;
                div.onclick = (e) => {
                    if (e.target.tagName === 'INPUT') {
                        if (e.target.checked) selectedParticipants.push(u);
                        else selectedParticipants = selectedParticipants.filter(p => p.email !== u.email);
                    }
                };
                groupUserList.appendChild(div);
            });
        }
    }

    async function fetchDashboardData() {
        try {
            // 1. Fetch and render current DB data immediately (Fast)
            const [summaryRes, meetingsRes] = await Promise.all([
                fetch('/api/summary'),
                fetch('/api/meetings')
            ]);
            updateSummaryCards(await summaryRes.json());
            renderMeetingsTable(await meetingsRes.json());
            
            // 2. Trigger sync in background (Slow) - don't await
            fetch('/api/sync-responses')
                .then(res => res.json())
                .then(result => {
                    if (result.success && result.synced > 0) {
                        // Refresh data again if any status changed
                        fetchDashboardDataOnly();
                    }
                });
        } catch (err) { console.error('Data fetch error:', err); }
    }

    async function fetchDashboardDataOnly() {
        try {
            const [summaryRes, meetingsRes] = await Promise.all([
                fetch('/api/summary'),
                fetch('/api/meetings')
            ]);
            updateSummaryCards(await summaryRes.json());
            renderMeetingsTable(await meetingsRes.json());
        } catch (err) { console.error('Data refresh error:', err); }
    }

    async function fetchUsers() {
        try {
            const res = await fetch('/api/users');
            allUsers = await res.json();
            renderUsersTable(allUsers);
        } catch (err) { console.error('User fetch error:', err); }
    }

    function updateSummaryCards(summary) {
        totalMeetingsEl.innerText = summary.total;
        upcomingMeetingsEl.innerText = summary.upcoming;
        acceptedMeetingsEl.innerText = summary.accepted;
        declinedMeetingsEl.innerText = summary.declined;
    }

    function formatTime(time24) {
        if (!time24) return '';
        const [hours, minutes] = time24.split(':');
        let h = parseInt(hours);
        const ampm = h >= 12 ? 'PM' : 'AM';
        h = h % 12 || 12;
        return `${h}:${minutes} ${ampm}`;
    }

    function renderMeetingsTable(data) {
        meetingsBody.innerHTML = '';
        data.forEach(m => {
            let meetLinkHtml = '';
            
            if (m.send_status === 'pending' && m.scheduled_send_time) {
                // Parse the local time (YYYY-MM-DDTHH:MM)
                const scheduledDate = new Date(m.scheduled_send_time);
                const now = new Date();
                
                if (scheduledDate > now) {
                    const diffMs = scheduledDate - now;
                    const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
                    const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
                    
                    let timeLeft = '';
                    if (diffHrs > 24) {
                        timeLeft = `in ${Math.floor(diffHrs/24)}d ${diffHrs%24}h`;
                    } else if (diffHrs > 0) {
                        timeLeft = `in ${diffHrs}h ${diffMins}m`;
                    } else {
                        timeLeft = `in ${diffMins}m`;
                    }
                    meetLinkHtml = `<span style="color: #F59E0B; font-size: 0.9em;"><i class="fas fa-clock"></i> Sends ${timeLeft}</span>`;
                } else {
                    meetLinkHtml = `<span style="color: #F59E0B; font-size: 0.9em;"><i class="fas fa-spinner fa-spin"></i> Sending now...</span>`;
                }
            } else if (m.meet_link && m.meet_link.startsWith('http')) {
                meetLinkHtml = `<a href="${m.meet_link}" target="_blank" class="meet-link"><i class="fas fa-video"></i> Join</a>`;
            } else {
                meetLinkHtml = `<span class="text-muted">${m.meet_link || 'N/A'}</span>`;
            }

            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${m.title}</strong></td>
                <td><span class="text-muted">${m.participants_summary || 'None'}</span></td>
                <td>${m.date} | ${formatTime(m.time)}</td>
                <td>${meetLinkHtml}</td>
                <td><span class="status-badge ${m.status}">${m.status.charAt(0).toUpperCase() + m.status.slice(1)}</span></td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-secondary btn-icon" title="View Details" onclick="viewDetails(${m.id})"><i class="fas fa-eye"></i></button>
                        <button class="btn btn-secondary btn-icon" title="Copy Link" onclick="copyLink('${m.meet_link}')"><i class="fas fa-copy"></i></button>
                        <button class="btn btn-secondary btn-icon delete-btn" title="Delete Meeting" onclick="handleDeleteMeeting(${m.id})"><i class="fas fa-trash"></i></button>
                    </div>
                </td>
            `;
            meetingsBody.appendChild(row);
        });
    }

    window.handleDeleteMeeting = async (id) => {
        if (!confirm('Are you sure you want to delete this meeting? This will also cancel the Google Calendar event.')) return;
        
        try {
            const res = await fetch(`/api/meetings/${id}`, { method: 'DELETE' });
            const result = await res.json();
            if (result.success) {
                fetchDashboardData();
            } else {
                alert('Failed to delete meeting: ' + (result.error || 'Unknown error'));
            }
        } catch (err) { alert('Connection error'); }
    };

    function renderUsersTable(data) {
        usersBody.innerHTML = '';
        data.forEach(u => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${u.name}</strong></td>
                <td>${u.email}</td>
                <td>
                    <button class="btn btn-secondary btn-icon delete-btn" onclick="handleDeleteUser('${u.email}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            usersBody.appendChild(row);
        });
    }

    async function handleCreateMeeting() {
        const title = meetTitle.value.trim();
        const date = meetDate.value;
        const agenda = meetAgenda.value.trim();

        // Construct 24h time from dropdowns
        let h = parseInt(timeHour.value);
        const m = timeMinute.value.padStart(2, '0');
        const ampm = timeAmpm.value;
        
        if (ampm === 'PM' && h < 12) h += 12;
        if (ampm === 'AM' && h === 12) h = 0;
        const timeVal = `${h.toString().padStart(2, '0')}:${m}`;

        const deliveryMode = document.getElementById('emailDeliveryMode').value;
        let scheduledTime = null;

        if (deliveryMode === 'custom') {
            const dDate = delayDate.value;
            let dH = parseInt(delayHour.value);
            const dM = delayMinute.value.padStart(2, '0');
            const dAmpm = delayAmpm.value;
            
            if (!dDate) {
                alert('Please select a custom date for the email delivery.');
                return;
            }
            
            if (dAmpm === 'PM' && dH < 12) dH += 12;
            if (dAmpm === 'AM' && dH === 12) dH = 0;
            const dTimeVal = `${dH.toString().padStart(2, '0')}:${dM}`;
            
            scheduledTime = `${dDate}T${dTimeVal}`;
        }

        if (!title || !date || !agenda) {
            alert('Please fill all fields, including the agenda.');
            return;
        }

        wizardSubmitBtn.disabled = true;
        document.getElementById('btnSpinner').classList.remove('hidden');

        try {
            const res = await fetch('/api/create-meeting', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    date,
                    time: timeVal,
                    agenda,
                    participants: selectedParticipants,
                    send_status: deliveryMode === 'custom' ? 'pending' : 'sent',
                    scheduled_send_time: deliveryMode === 'custom' ? scheduledTime : null
                })
            });
            const result = await res.json();
            if (result.success) {
                creationResult.innerText = '✅ Meeting created!';
                creationResult.className = 'result-msg msg-success';
                fetchDashboardData();
                setTimeout(() => createModal.style.display = 'none', 1500);
            } else {
                creationResult.innerText = '❌ ' + (result.error || 'Error');
                creationResult.className = 'result-msg msg-error';
            }
        } catch (err) { creationResult.innerText = '❌ Connection failed.'; }
        finally { 
            creationResult.classList.remove('hidden'); 
            wizardSubmitBtn.disabled = false; 
            document.getElementById('btnSpinner').classList.add('hidden');
        }
    }

    async function handleAddUser() {
        const name = document.getElementById('userName').value.trim();
        const email = document.getElementById('userEmail').value.trim();
        if (!name || !email) return;

        userBtnText.innerText = 'Adding...';
        saveUserBtn.disabled = true;

        try {
            const res = await fetch('/api/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email })
            });
            const result = await res.json();
            if (result.success) {
                userResult.innerText = '✅ User added!';
                userResult.className = 'result-msg msg-success';
                document.getElementById('userName').value = '';
                document.getElementById('userEmail').value = '';
                fetchUsers();
                setTimeout(() => userModal.style.display = 'none', 1000);
            } else {
                userResult.innerText = '❌ Failed (Check if email exists)';
                userResult.className = 'result-msg msg-error';
            }
        } catch (err) { userResult.innerText = '❌ Error adding user.'; }
        finally { userResult.classList.remove('hidden'); userBtnText.innerText = 'Add User'; saveUserBtn.disabled = false; }
    }

    window.handleDeleteUser = async (email) => {
        if (!confirm(`Delete ${email}?`)) return;
        try {
            await fetch(`/api/users/${email}`, { method: 'DELETE' });
            fetchUsers();
        } catch (err) { alert('Delete failed'); }
    }

    window.viewDetails = async (id) => {
        const res = await fetch(`/api/meetings/${id}`);
        const data = await res.json();
        const m = data.meeting;
        const p = data.participants;
        document.getElementById('detailBody').innerHTML = `
            <div class="detail-section" style="margin-bottom: 20px;">
                <p style="margin: 5px 0;"><strong>Title:</strong> ${m.title}</p>
                <p style="margin: 5px 0;"><strong>Date & Time:</strong> ${m.date} at ${formatTime(m.time)}</p>
                <p style="margin: 5px 0; margin-top: 15px;"><strong>Agenda:</strong></p>
                <div class="agenda-box" style="background: var(--bg-lighter); padding: 10px; border-radius: 8px; font-size: 0.9em; max-height: 100px; overflow-y: auto;">
                    ${m.agenda.replace(/\n/g, '<br>')}
                </div>
            </div>
            <h3 style="font-size: 1.1em; color: var(--primary-light); margin-bottom: 15px; border-bottom: 1px solid var(--border-color); padding-bottom: 5px;">Participants Status</h3>
            <div class="participant-list" style="display: flex; flex-direction: column; gap: 10px;">
                ${p.map(part => `
                    <div class="participant-item" style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); padding: 12px 15px; border-radius: 8px; border: 1px solid var(--border-color);">
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <span style="font-size: 1.05em; font-weight: 500;">${part.name} <span style="font-size: 0.9em; color: var(--text-muted); font-weight: normal;">(${part.email})</span></span>
                            <span style="font-size: 0.85em; color: var(--text-muted);">
                                <i class="fas fa-paper-plane" style="color: var(--primary-color);"></i> Follow-ups Sent: <strong>${part.followup_count || 0}/3</strong> 
                                ${part.last_followup_time ? `(Last: ${part.last_followup_time.split(' ')[1].slice(0,5)})` : ''}
                            </span>
                        </div>
                        <span class="status-badge ${part.status}" style="padding: 6px 12px; font-size: 0.8em;">${part.status.toUpperCase()}</span>
                    </div>
                `).join('')}
            </div>
        `;
        detailsModal.style.display = 'flex';
    };

    window.copyLink = (link) => {
        navigator.clipboard.writeText(link);
        alert('Copied!');
    };

    // =============================================
    // --- Real-Time Notification System ---
    // =============================================

    const seenNotifIds = new Set();
    let notifUnreadCount = 0;
    let notifDropdownOpen = false;

    function initNotifications() {
        // 1. Request browser notification permission
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().then(perm => {
                console.log('[NOTIF] Permission:', perm);
            });
        }

        // 2. Bell click toggle
        const bellBtn = document.getElementById('notifBellBtn');
        const dropdown = document.getElementById('notifDropdown');

        bellBtn.onclick = (e) => {
            e.stopPropagation();
            notifDropdownOpen = !notifDropdownOpen;
            dropdown.classList.toggle('hidden', !notifDropdownOpen);
            if (notifDropdownOpen) {
                loadRecentNotifications();
            }
        };

        // Close dropdown on outside click
        document.addEventListener('click', (e) => {
            if (!document.getElementById('notifWrapper').contains(e.target)) {
                dropdown.classList.add('hidden');
                notifDropdownOpen = false;
            }
        });

        // Clear button
        document.getElementById('notifClearBtn').onclick = () => {
            document.getElementById('notifDropdownBody').innerHTML = '<p class="notif-empty">No new notifications</p>';
            notifUnreadCount = 0;
            updateBadge();
        };

        // 3. Start polling every 5 seconds
        pollNotifications();
        setInterval(pollNotifications, 5000);
    }

    async function pollNotifications() {
        try {
            const res = await fetch('/api/notifications');
            const data = await res.json();

            if (data.notifications && data.notifications.length > 0) {
                data.notifications.forEach(n => {
                    if (!seenNotifIds.has(n.id)) {
                        seenNotifIds.add(n.id);
                        notifUnreadCount++;
                        showBrowserNotification(n.message);
                        prependToDropdown(n);
                    }
                });
                updateBadge();
            }
        } catch (err) {
            // Silently fail — don't break the UI
            console.warn('[NOTIF] Poll error:', err);
        }
    }

    function showBrowserNotification(message) {
        if ('Notification' in window && Notification.permission === 'granted') {
            try {
                new Notification('Scheduler AI', {
                    body: message,
                    icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">📅</text></svg>',
                    tag: 'scheduler-' + Date.now()
                });
            } catch (e) {
                console.warn('[NOTIF] Browser notification failed:', e);
            }
        }
    }

    function prependToDropdown(notif) {
        const body = document.getElementById('notifDropdownBody');
        // Remove empty message if present
        const emptyMsg = body.querySelector('.notif-empty');
        if (emptyMsg) emptyMsg.remove();

        const div = document.createElement('div');
        div.className = 'notif-item unseen';
        const timeStr = notif.created_at ? notif.created_at.split(' ')[1] || '' : '';
        div.innerHTML = `
            ${notif.message}
            <span class="notif-time">${timeStr}</span>
        `;
        body.prepend(div);
    }

    function updateBadge() {
        const badge = document.getElementById('notifBadge');
        if (notifUnreadCount > 0) {
            badge.textContent = notifUnreadCount > 99 ? '99+' : notifUnreadCount;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    async function loadRecentNotifications() {
        try {
            const res = await fetch('/api/notifications/recent');
            const data = await res.json();
            const body = document.getElementById('notifDropdownBody');

            if (data.notifications && data.notifications.length > 0) {
                body.innerHTML = '';
                data.notifications.forEach(n => {
                    seenNotifIds.add(n.id);
                    const div = document.createElement('div');
                    div.className = 'notif-item' + (n.seen === 0 ? ' unseen' : '');
                    const timeStr = n.created_at ? n.created_at.split(' ')[1] || '' : '';
                    div.innerHTML = `
                        ${n.message}
                        <span class="notif-time">${timeStr}</span>
                    `;
                    body.appendChild(div);
                });
            } else {
                body.innerHTML = '<p class="notif-empty">No notifications yet</p>';
            }

            // Reset badge when user opens dropdown
            notifUnreadCount = 0;
            updateBadge();
        } catch (err) {
            console.warn('[NOTIF] Load recent error:', err);
        }
    }
});
