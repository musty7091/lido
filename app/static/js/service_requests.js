document.addEventListener("DOMContentLoaded", function () {
    const serviceRequestsButton = document.getElementById("serviceRequestsButton");
    const serviceRequestsPanel = document.getElementById("serviceRequestsPanel");
    const serviceRequestsCount = document.getElementById("serviceRequestsCount");
    const serviceRequestsList = document.getElementById("serviceRequestsList");
    const serviceRequestsEmpty = document.getElementById("serviceRequestsEmpty");

    if (!serviceRequestsButton || !serviceRequestsPanel || !serviceRequestsCount || !serviceRequestsList) {
        return;
    }

    const csrfTokenElement = document.querySelector("meta[name='csrf-token']");
    const csrfToken = csrfTokenElement ? csrfTokenElement.getAttribute("content") : "";

    const ALERT_MIN_INTERVAL_MS = 2400;
    const REMINDER_AFTER_MS = 30000;
    const REMINDER_INTERVAL_MS = 30000;
    const POLL_INTERVAL_MS = 8000;

    let isPanelOpen = false;
    let firstFetchCompleted = false;
    let knownServiceRequestIds = new Set();
    let openRequestFirstSeenAt = new Map();
    let openRequestLastAlertAt = new Map();
    let audioContext = null;
    let soundUnlocked = false;
    let lastSoundPlayedAt = 0;
    let pendingUnlockPromise = null;

    function escapeHtml(value) {
        const text = value === null || value === undefined ? "" : String(value);

        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function getAudioContext() {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;

        if (!AudioContextClass) {
            return null;
        }

        if (!audioContext) {
            audioContext = new AudioContextClass();
        }

        return audioContext;
    }

    function markSoundReady(context) {
        if (context && context.state === "running") {
            soundUnlocked = true;
            serviceRequestsButton.classList.add("sound-ready");
            serviceRequestsButton.classList.remove("sound-locked");
        }
    }

    function unlockNotificationSound() {
        const context = getAudioContext();

        if (!context) {
            return;
        }

        if (context.state === "running") {
            markSoundReady(context);
            return;
        }

        if (!pendingUnlockPromise && context.state === "suspended") {
            pendingUnlockPromise = context.resume()
                .then(function () {
                    markSoundReady(context);
                })
                .catch(function () {
                    serviceRequestsButton.classList.add("sound-locked");
                })
                .finally(function () {
                    pendingUnlockPromise = null;
                });
        }
    }

    function createMasterGain(context, startTime, duration, peakGain) {
        const masterGain = context.createGain();

        masterGain.gain.setValueAtTime(0.0001, startTime);
        masterGain.gain.linearRampToValueAtTime(peakGain, startTime + 0.035);
        masterGain.gain.setValueAtTime(peakGain, startTime + Math.max(0.05, duration - 0.12));
        masterGain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
        masterGain.connect(context.destination);

        return masterGain;
    }

    function playTone(context, destination, startTime, frequency, duration, oscillatorType) {
        const oscillator = context.createOscillator();
        const gainNode = context.createGain();

        oscillator.type = oscillatorType || "sine";
        oscillator.frequency.setValueAtTime(frequency, startTime);

        gainNode.gain.setValueAtTime(0.0001, startTime);
        gainNode.gain.linearRampToValueAtTime(1.0, startTime + 0.025);
        gainNode.gain.setValueAtTime(1.0, startTime + Math.max(0.035, duration - 0.07));
        gainNode.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

        oscillator.connect(gainNode);
        gainNode.connect(destination);

        oscillator.start(startTime);
        oscillator.stop(startTime + duration + 0.04);
    }

    function playServiceCallSound(isReminder) {
        const now = Date.now();

        if (now - lastSoundPlayedAt < ALERT_MIN_INTERVAL_MS) {
            return false;
        }

        const context = getAudioContext();

        if (!context) {
            return false;
        }

        if (context.state === "suspended") {
            unlockNotificationSound();
            return false;
        }

        if (!soundUnlocked || context.state !== "running") {
            return false;
        }

        try {
            const startTime = context.currentTime + 0.03;
            const masterGain = createMasterGain(
                context,
                startTime,
                isReminder ? 0.72 : 0.95,
                isReminder ? 0.62 : 0.78
            );

            if (isReminder) {
                // Daha kısa ve daha kibar hatırlatma tonu.
                playTone(context, masterGain, startTime, 784, 0.22, "triangle");
                playTone(context, masterGain, startTime + 0.20, 1046, 0.26, "triangle");
                playTone(context, masterGain, startTime, 392, 0.36, "sine");
            } else {
                // Personel cihazında duyulabilecek, ama alarm gibi rahatsız etmeyen çift vuruşlu çağrı tonu.
                playTone(context, masterGain, startTime, 659, 0.20, "triangle");
                playTone(context, masterGain, startTime + 0.16, 880, 0.24, "triangle");
                playTone(context, masterGain, startTime + 0.42, 784, 0.22, "triangle");
                playTone(context, masterGain, startTime + 0.58, 1175, 0.28, "sine");

                // Laptop/tablet hoparlörlerinde ince ses kaybolmasın diye alttan yumuşak gövde tonu.
                playTone(context, masterGain, startTime, 330, 0.52, "sine");
                playTone(context, masterGain, startTime + 0.42, 392, 0.46, "sine");
            }

            lastSoundPlayedAt = now;
            return true;
        } catch (error) {
            return false;
        }
    }

    function vibrateForNewRequest(isReminder) {
        if (!navigator.vibrate) {
            return false;
        }

        try {
            if (isReminder) {
                navigator.vibrate([220, 80, 220]);
            } else {
                navigator.vibrate([320, 90, 320, 100, 520]);
            }

            return true;
        } catch (error) {
            return false;
        }
    }

    function triggerStaffDeviceAlert(isReminder) {
        unlockNotificationSound();
        const soundPlayed = playServiceCallSound(Boolean(isReminder));
        const vibrationStarted = vibrateForNewRequest(Boolean(isReminder));

        if (!soundPlayed && !vibrationStarted) {
            serviceRequestsButton.classList.add("sound-locked");
        }
    }

    function setPanelOpen(open) {
        isPanelOpen = open;

        if (isPanelOpen) {
            serviceRequestsPanel.classList.add("is-open");
            serviceRequestsButton.setAttribute("aria-expanded", "true");
        } else {
            serviceRequestsPanel.classList.remove("is-open");
            serviceRequestsButton.setAttribute("aria-expanded", "false");
        }
    }

    function getStatusClass(status) {
        if (status === "open") {
            return "service-request-status-open";
        }

        if (status === "seen") {
            return "service-request-status-seen";
        }

        return "service-request-status-neutral";
    }

    function buildRequestRow(serviceRequest) {
        const noteHtml = serviceRequest.note
            ? `<p class="service-request-note">${escapeHtml(serviceRequest.note)}</p>`
            : "";

        const seenButton = serviceRequest.status === "open"
            ? `<button type="button" class="service-request-action-button" data-service-request-action="seen" data-service-request-id="${serviceRequest.id}">Gördüm</button>`
            : "";

        return `
            <article class="service-request-row ${getStatusClass(serviceRequest.status)}">
                <div class="service-request-row-main">
                    <div class="service-request-row-title">
                        <strong>${escapeHtml(serviceRequest.table_code)} / ${escapeHtml(serviceRequest.area_name)}</strong>
                        <span>${escapeHtml(serviceRequest.elapsed_text)}</span>
                    </div>
                    <div class="service-request-row-subtitle">
                        ${escapeHtml(serviceRequest.request_type_label)} · ${escapeHtml(serviceRequest.status_label)}
                    </div>
                    ${noteHtml}
                </div>
                <div class="service-request-row-actions">
                    ${seenButton}
                    <button type="button" class="service-request-action-button service-request-complete-button" data-service-request-action="complete" data-service-request-id="${serviceRequest.id}">Tamamlandı</button>
                </div>
            </article>
        `;
    }

    function updateOpenRequestTracking(serviceRequests) {
        const now = Date.now();
        const currentOpenIds = new Set();

        serviceRequests.forEach(function (serviceRequest) {
            const requestId = String(serviceRequest.id);

            if (serviceRequest.status !== "open") {
                return;
            }

            currentOpenIds.add(requestId);

            if (!openRequestFirstSeenAt.has(requestId)) {
                openRequestFirstSeenAt.set(requestId, now);
            }
        });

        Array.from(openRequestFirstSeenAt.keys()).forEach(function (requestId) {
            if (!currentOpenIds.has(requestId)) {
                openRequestFirstSeenAt.delete(requestId);
                openRequestLastAlertAt.delete(requestId);
            }
        });
    }

    function detectNewServiceRequests(serviceRequests) {
        const currentIds = new Set();
        let hasNewRequest = false;

        serviceRequests.forEach(function (serviceRequest) {
            const requestId = String(serviceRequest.id);
            currentIds.add(requestId);

            if (firstFetchCompleted && !knownServiceRequestIds.has(requestId)) {
                hasNewRequest = true;
                openRequestLastAlertAt.set(requestId, Date.now());
            }
        });

        knownServiceRequestIds = currentIds;

        if (!firstFetchCompleted) {
            firstFetchCompleted = true;
            return false;
        }

        return hasNewRequest;
    }

    function shouldSendReminderForOpenRequests(serviceRequests) {
        const now = Date.now();
        let shouldRemind = false;

        serviceRequests.forEach(function (serviceRequest) {
            if (serviceRequest.status !== "open") {
                return;
            }

            const requestId = String(serviceRequest.id);
            const firstSeenAt = openRequestFirstSeenAt.get(requestId) || now;
            const lastAlertAt = openRequestLastAlertAt.get(requestId) || firstSeenAt;

            if (now - firstSeenAt >= REMINDER_AFTER_MS && now - lastAlertAt >= REMINDER_INTERVAL_MS) {
                openRequestLastAlertAt.set(requestId, now);
                shouldRemind = true;
            }
        });

        return shouldRemind;
    }

    function triggerNewRequestAlert(isReminder) {
        serviceRequestsButton.classList.add("has-new-request");
        triggerStaffDeviceAlert(Boolean(isReminder));

        window.setTimeout(function () {
            serviceRequestsButton.classList.remove("has-new-request");
        }, isReminder ? 2600 : 5000);
    }

    function renderServiceRequests(data) {
        const serviceRequests = Array.isArray(data.service_requests) ? data.service_requests : [];
        const count = Number(data.count || serviceRequests.length || 0);

        updateOpenRequestTracking(serviceRequests);

        const hasNewRequest = detectNewServiceRequests(serviceRequests);
        const hasOpenRequests = serviceRequests.some(function (serviceRequest) {
            return serviceRequest.status === "open";
        });
        const shouldRemind = !hasNewRequest && firstFetchCompleted && shouldSendReminderForOpenRequests(serviceRequests);

        serviceRequestsCount.textContent = count;
        serviceRequestsButton.classList.toggle("has-active-requests", count > 0);
        serviceRequestsButton.classList.toggle("has-unseen-requests", hasOpenRequests);

        if (hasNewRequest) {
            triggerNewRequestAlert(false);
        } else if (shouldRemind) {
            triggerNewRequestAlert(true);
        }

        if (count === 0) {
            serviceRequestsList.innerHTML = "";

            if (serviceRequestsEmpty) {
                serviceRequestsEmpty.classList.remove("is-hidden");
            }

            return;
        }

        if (serviceRequestsEmpty) {
            serviceRequestsEmpty.classList.add("is-hidden");
        }

        serviceRequestsList.innerHTML = serviceRequests.map(buildRequestRow).join("");
    }

    async function fetchActiveServiceRequests() {
        try {
            const response = await fetch("/api/service-requests/active", {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                },
            });

            if (!response.ok) {
                return;
            }

            const data = await response.json();

            if (data && data.success) {
                renderServiceRequests(data);
            }
        } catch (error) {
            // Bağlantı anlık koparsa kullanıcıyı rahatsız etmeden sonraki kontrole bırakılır.
        }
    }

    async function postServiceRequestAction(serviceRequestId, action) {
        const endpoint = `/api/service-requests/${serviceRequestId}/${action}`;

        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({}),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || "Çağrı güncellenirken hata oluştu.");
        }

        return data;
    }

    document.addEventListener("pointerdown", unlockNotificationSound, { once: true });
    document.addEventListener("click", unlockNotificationSound, { once: true });
    document.addEventListener("keydown", unlockNotificationSound, { once: true });
    document.addEventListener("touchstart", unlockNotificationSound, { once: true });

    serviceRequestsButton.addEventListener("click", function () {
        unlockNotificationSound();
        setPanelOpen(!isPanelOpen);
        fetchActiveServiceRequests();
    });

    document.addEventListener("click", function (event) {
        if (!isPanelOpen) {
            return;
        }

        if (serviceRequestsPanel.contains(event.target) || serviceRequestsButton.contains(event.target)) {
            return;
        }

        setPanelOpen(false);
    });

    serviceRequestsList.addEventListener("click", async function (event) {
        const actionButton = event.target.closest("[data-service-request-action]");

        if (!actionButton) {
            return;
        }

        const serviceRequestId = actionButton.dataset.serviceRequestId;
        const action = actionButton.dataset.serviceRequestAction;
        const normalText = actionButton.textContent;

        actionButton.disabled = true;
        actionButton.textContent = "İşleniyor...";

        try {
            await postServiceRequestAction(serviceRequestId, action);
            await fetchActiveServiceRequests();
        } catch (error) {
            alert(error.message);
            actionButton.disabled = false;
            actionButton.textContent = normalText;
        }
    });

    serviceRequestsButton.classList.add("sound-locked");

    fetchActiveServiceRequests();
    window.setInterval(fetchActiveServiceRequests, POLL_INTERVAL_MS);
});
