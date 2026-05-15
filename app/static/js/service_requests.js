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

    let isPanelOpen = false;
    let firstFetchCompleted = false;
    let knownServiceRequestIds = new Set();
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
        }
    }

    function unlockNotificationSound() {
        const context = getAudioContext();

        if (!context) {
            return;
        }

        if (context.state === "running") {
            soundUnlocked = true;
            return;
        }

        if (!pendingUnlockPromise && context.state === "suspended") {
            pendingUnlockPromise = context.resume()
                .then(function () {
                    markSoundReady(context);
                })
                .catch(function () {
                    // Tarayıcı ses izni vermezse sessiz devam edilir.
                })
                .finally(function () {
                    pendingUnlockPromise = null;
                });
        }
    }

    function playTone(context, startTime, frequency, duration, peakGain) {
        const oscillator = context.createOscillator();
        const gainNode = context.createGain();

        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(frequency, startTime);

        gainNode.gain.setValueAtTime(0.0001, startTime);
        gainNode.gain.exponentialRampToValueAtTime(peakGain, startTime + 0.018);
        gainNode.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

        oscillator.connect(gainNode);
        gainNode.connect(context.destination);

        oscillator.start(startTime);
        oscillator.stop(startTime + duration + 0.03);
    }

    function playSoftNotificationSound() {
        const now = Date.now();

        if (now - lastSoundPlayedAt < 2500) {
            return;
        }

        const context = getAudioContext();

        if (!context) {
            return;
        }

        if (context.state === "suspended") {
            context.resume()
                .then(function () {
                    soundUnlocked = true;
                    playSoftNotificationSound();
                })
                .catch(function () {
                    // Tarayıcı ses izni vermezse sessiz devam edilir.
                });
            return;
        }

        if (!soundUnlocked || context.state !== "running") {
            return;
        }

        try {
            const startTime = context.currentTime + 0.015;

            playTone(context, startTime, 880, 0.16, 0.12);
            playTone(context, startTime + 0.14, 1175, 0.19, 0.09);

            lastSoundPlayedAt = now;
        } catch (error) {
            // Ses üretilemezse çağrı merkezi çalışmaya devam eder.
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

    function detectNewServiceRequests(serviceRequests) {
        const currentIds = new Set();
        let hasNewRequest = false;

        serviceRequests.forEach(function (serviceRequest) {
            const requestId = String(serviceRequest.id);
            currentIds.add(requestId);

            if (firstFetchCompleted && !knownServiceRequestIds.has(requestId)) {
                hasNewRequest = true;
            }
        });

        knownServiceRequestIds = currentIds;

        if (!firstFetchCompleted) {
            firstFetchCompleted = true;
            return false;
        }

        return hasNewRequest;
    }

    function triggerNewRequestAlert() {
        serviceRequestsButton.classList.add("has-new-request");
        playSoftNotificationSound();

        window.setTimeout(function () {
            serviceRequestsButton.classList.remove("has-new-request");
        }, 4000);
    }

    function renderServiceRequests(data) {
        const serviceRequests = Array.isArray(data.service_requests) ? data.service_requests : [];
        const count = Number(data.count || serviceRequests.length || 0);
        const hasNewRequest = detectNewServiceRequests(serviceRequests);

        serviceRequestsCount.textContent = count;
        serviceRequestsButton.classList.toggle("has-active-requests", count > 0);

        if (hasNewRequest) {
            triggerNewRequestAlert();
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

    fetchActiveServiceRequests();
    window.setInterval(fetchActiveServiceRequests, 8000);
});
