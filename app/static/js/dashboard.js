document.addEventListener("DOMContentLoaded", function () {
    const tableCards = Array.from(document.querySelectorAll("[data-table-card]"));
    const areaButtons = Array.from(document.querySelectorAll("[data-area-button]"));
    const occupancyBars = Array.from(document.querySelectorAll("[data-occupancy-rate]"));

    const csrfTokenElement = document.querySelector("meta[name='csrf-token']");
    const csrfToken = csrfTokenElement ? csrfTokenElement.getAttribute("content") : "";

    const tableSearchInput = document.getElementById("tableSearchInput");
    const statusFilter = document.getElementById("statusFilter");
    const clearFiltersButton = document.getElementById("clearFiltersButton");
    const visibleTableCount = document.getElementById("visibleTableCount");
    const tablePanelTitle = document.getElementById("tablePanelTitle");

    const assignmentPanel = document.getElementById("assignmentPanel");
    const mobilePanelBackdrop = document.getElementById("mobilePanelBackdrop");
    const mobilePanelCloseButton = document.getElementById("mobilePanelCloseButton");

    const selectedTableCode = document.getElementById("selectedTableCode");
    const selectedTableDescription = document.getElementById("selectedTableDescription");
    const selectedTableStatus = document.getElementById("selectedTableStatus");
    const selectedTableDuration = document.getElementById("selectedTableDuration");

    const selectedReservationBox = document.getElementById("selectedReservationBox");
    const selectedReservationIcon = document.getElementById("selectedReservationIcon");
    const selectedReservationTitle = document.getElementById("selectedReservationTitle");
    const selectedReservationSummary = document.getElementById("selectedReservationSummary");
    const selectedReservationDateText = document.getElementById("selectedReservationDateText");
    const selectedReservationPartyText = document.getElementById("selectedReservationPartyText");
    const selectedReservationCustomerText = document.getElementById("selectedReservationCustomerText");
    const selectedReservationPhoneText = document.getElementById("selectedReservationPhoneText");
    const selectedReservationDepositText = document.getElementById("selectedReservationDepositText");
    const selectedReservationProtectionText = document.getElementById("selectedReservationProtectionText");
    const selectedReservationNoteBox = document.getElementById("selectedReservationNoteBox");
    const selectedReservationNoteText = document.getElementById("selectedReservationNoteText");
    const editReservationButton = document.getElementById("editReservationButton");
    const cancelReservationButton = document.getElementById("cancelReservationButton");

    const idlePanel = document.getElementById("idlePanel");
    const emptyTablePanel = document.getElementById("emptyTablePanel");
    const activeTablePanel = document.getElementById("activeTablePanel");
    const inactiveTablePanel = document.getElementById("inactiveTablePanel");

    const selectedPartySizeText = document.getElementById("selectedPartySizeText");
    const selectedCustomerNameText = document.getElementById("selectedCustomerNameText");
    const selectedCustomerPhoneText = document.getElementById("selectedCustomerPhoneText");
    const selectedCheckInText = document.getElementById("selectedCheckInText");
    const selectedCustomerNoteText = document.getElementById("selectedCustomerNoteText");

    const personCountInput = document.getElementById("personCountInput");
    const decreasePersonButton = document.getElementById("decreasePersonButton");
    const increasePersonButton = document.getElementById("increasePersonButton");
    const assignButton = document.getElementById("assignButton");

    const customerNameInput = document.getElementById("customerNameInput");
    const customerPhoneInput = document.getElementById("customerPhoneInput");
    const customerNoteInput = document.getElementById("customerNoteInput");

    const clearTableButton = document.getElementById("clearTableButton");

    const selectedServiceRequestBox = document.getElementById("selectedServiceRequestBox");
    const selectedServiceRequestText = document.getElementById("selectedServiceRequestText");

    const transferTargetTableSelect = document.getElementById("transferTargetTableSelect");
    const transferTableButton = document.getElementById("transferTableButton");

    let selectedTable = null;
    let activeAreaKey = "all";
    let activeAreaName = "Tüm Masalar";

    function isMobileActionPanelMode() {
        return window.matchMedia("(max-width: 820px)").matches;
    }

    function openMobileActionPanel() {
        if (!assignmentPanel || !isMobileActionPanelMode()) {
            return;
        }

        assignmentPanel.classList.add("is-mobile-open");

        if (mobilePanelBackdrop) {
            mobilePanelBackdrop.classList.add("is-visible");
        }

        document.body.classList.add("mobile-action-open");
    }

    function closeMobileActionPanel() {
        if (assignmentPanel) {
            assignmentPanel.classList.remove("is-mobile-open");
        }

        if (mobilePanelBackdrop) {
            mobilePanelBackdrop.classList.remove("is-visible");
        }

        document.body.classList.remove("mobile-action-open");
    }

    function handleViewportChange() {
        if (!isMobileActionPanelMode()) {
            closeMobileActionPanel();
        }
    }

    function initializeOccupancyBars() {
        occupancyBars.forEach(function (bar) {
            const rawRate = bar.dataset.occupancyRate;
            let parsedRate = Number.parseFloat(rawRate);

            if (Number.isNaN(parsedRate)) {
                parsedRate = 0;
            }

            if (parsedRate < 0) {
                parsedRate = 0;
            }

            if (parsedRate > 100) {
                parsedRate = 100;
            }

            bar.style.width = `${parsedRate}%`;
        });
    }

    function getStatusClass(status) {
        if (status === "empty") {
            return "status-empty";
        }

        if (status === "occupied") {
            return "status-occupied";
        }

        if (status === "long") {
            return "status-long";
        }

        if (status === "inactive") {
            return "status-inactive";
        }

        return "status-neutral";
    }

    function clearStatusClasses(element) {
        element.classList.remove(
            "status-neutral",
            "status-empty",
            "status-occupied",
            "status-long",
            "status-inactive"
        );
    }

    function valueOrDash(value) {
        if (value === null || value === undefined) {
            return "-";
        }

        const cleanedValue = String(value).trim();

        if (cleanedValue === "") {
            return "-";
        }

        return cleanedValue;
    }

    function hideAllPanels() {
        idlePanel.classList.add("is-hidden");
        emptyTablePanel.classList.add("is-hidden");
        activeTablePanel.classList.add("is-hidden");
        inactiveTablePanel.classList.add("is-hidden");
    }

    function showIdlePanel() {
        hideAllPanels();
        idlePanel.classList.remove("is-hidden");
    }

    function showEmptyTablePanel() {
        hideAllPanels();
        emptyTablePanel.classList.remove("is-hidden");
    }

    function showActiveTablePanel() {
        hideAllPanels();
        activeTablePanel.classList.remove("is-hidden");
    }

    function showInactiveTablePanel() {
        hideAllPanels();
        inactiveTablePanel.classList.remove("is-hidden");
    }

    function clearCustomerForm() {
        customerNameInput.value = "";
        customerPhoneInput.value = "";
        customerNoteInput.value = "";
    }

    function fillActiveCustomerInfo() {
        selectedPartySizeText.textContent = valueOrDash(selectedTable.partySize);
        selectedCustomerNameText.textContent = valueOrDash(selectedTable.customerName);
        selectedCustomerPhoneText.textContent = valueOrDash(selectedTable.customerPhone);
        selectedCheckInText.textContent = valueOrDash(selectedTable.checkInDisplay);
        selectedCustomerNoteText.textContent = valueOrDash(selectedTable.note);
    }

    function clearActiveCustomerInfo() {
        selectedPartySizeText.textContent = "-";
        selectedCustomerNameText.textContent = "-";
        selectedCustomerPhoneText.textContent = "-";
        selectedCheckInText.textContent = "-";
        selectedCustomerNoteText.textContent = "-";
    }

    function updateSelectedServiceRequestBox() {
        if (!selectedServiceRequestBox || !selectedServiceRequestText) {
            return;
        }

        if (!selectedTable || Number.parseInt(selectedTable.serviceRequestCount, 10) < 1) {
            selectedServiceRequestBox.classList.add("is-hidden");
            selectedServiceRequestText.textContent = "Bu masa için aktif çağrı bulunmuyor.";
            return;
        }

        selectedServiceRequestText.textContent = `${selectedTable.serviceRequestLabel} · ${selectedTable.serviceRequestCount} aktif çağrı`;
        selectedServiceRequestBox.classList.remove("is-hidden");
    }

    function getReservationTitleByState(state) {
        if (state === "protected") {
            return "Rezervasyon Korumasında";
        }

        if (state === "late") {
            return "Geciken Rezervasyon";
        }

        return "Yaklaşan Rezervasyon";
    }

    function updateSelectedReservationBox() {
        if (!selectedReservationBox) {
            return;
        }

        if (!selectedTable || selectedTable.reservationHas !== "1") {
            selectedReservationBox.classList.add("is-hidden");
            selectedReservationBox.classList.remove(
                "reservation-detail-protected",
                "reservation-detail-late",
                "reservation-detail-upcoming"
            );

            if (editReservationButton) {
                editReservationButton.disabled = true;
                editReservationButton.dataset.reservationId = "";
                editReservationButton.textContent = "Rezervasyonu Düzenle";
            }

            if (cancelReservationButton) {
                cancelReservationButton.disabled = true;
                cancelReservationButton.dataset.reservationId = "";
                cancelReservationButton.textContent = "Rezervasyonu İptal Et";
            }

            return;
        }

        const state = selectedTable.reservationState || "upcoming";
        const reservationTitle = getReservationTitleByState(state);
        const customerName = valueOrDash(selectedTable.reservationCustomerName);
        const phone = valueOrDash(selectedTable.reservationCustomerPhone);
        const partySize = valueOrDash(selectedTable.reservationPartySize);
        const reservationDate = valueOrDash(selectedTable.reservationDisplay);
        const depositDisplay = valueOrDash(selectedTable.reservationDepositDisplay);
        const protectionMinutes = valueOrDash(selectedTable.reservationProtectionMinutes);

        selectedReservationBox.classList.remove(
            "reservation-detail-protected",
            "reservation-detail-late",
            "reservation-detail-upcoming"
        );
        selectedReservationBox.classList.add(`reservation-detail-${state}`);

        if (selectedReservationIcon) {
            selectedReservationIcon.textContent = state === "late" ? "⚠" : "📅";
        }

        if (selectedReservationTitle) {
            selectedReservationTitle.textContent = reservationTitle;
        }

        if (selectedReservationSummary) {
            if (state === "protected") {
                selectedReservationSummary.textContent = "Bu masa koruma süresine girdi. Yeni müşteri ataması engellenir.";
            } else if (state === "late") {
                selectedReservationSummary.textContent = "Rezervasyon saati geçti. Müşteri geldiyse masaya alınmalı, gelmediyse takip edilmeli.";
            } else {
                selectedReservationSummary.textContent = "Bu masada ileri saat için onaylı rezervasyon var.";
            }
        }

        if (selectedReservationDateText) {
            selectedReservationDateText.textContent = reservationDate;
        }

        if (selectedReservationPartyText) {
            selectedReservationPartyText.textContent = `${partySize} kişi`;
        }

        if (selectedReservationCustomerText) {
            selectedReservationCustomerText.textContent = customerName;
        }

        if (selectedReservationPhoneText) {
            selectedReservationPhoneText.textContent = phone;
        }

        if (selectedReservationDepositText) {
            selectedReservationDepositText.textContent = depositDisplay;
        }

        if (selectedReservationProtectionText) {
            selectedReservationProtectionText.textContent = `${protectionMinutes} dk`;
        }

        if (selectedReservationNoteBox && selectedReservationNoteText) {
            const note = valueOrDash(selectedTable.reservationNote);

            if (note === "-") {
                selectedReservationNoteBox.classList.add("is-hidden");
                selectedReservationNoteText.textContent = "-";
            } else {
                selectedReservationNoteText.textContent = note;
                selectedReservationNoteBox.classList.remove("is-hidden");
            }
        }

        if (editReservationButton) {
            editReservationButton.disabled = false;
            editReservationButton.dataset.reservationId = selectedTable.reservationId || "";
            editReservationButton.textContent = "Rezervasyonu Düzenle";
        }

        if (cancelReservationButton) {
            cancelReservationButton.disabled = false;
            cancelReservationButton.dataset.reservationId = selectedTable.reservationId || "";
            cancelReservationButton.textContent = "Rezervasyonu İptal Et";
        }

        selectedReservationBox.classList.remove("is-hidden");
    }

    function setButtonLoading(button, isLoading, loadingText, normalText) {
        if (isLoading) {
            button.disabled = true;
            button.dataset.originalText = normalText;
            button.textContent = loadingText;
        } else {
            button.textContent = normalText;
        }
    }

    function getEmptyTableCardsForTransfer() {
        return tableCards.filter(function (card) {
            return card.dataset.status === "empty";
        });
    }

    function updateTransferPanel() {
        transferTargetTableSelect.innerHTML = "";

        if (!selectedTable || (selectedTable.status !== "occupied" && selectedTable.status !== "long")) {
            transferTargetTableSelect.disabled = true;
            transferTableButton.disabled = true;

            const option = document.createElement("option");
            option.value = "";
            option.textContent = "Önce dolu masa seçin";
            transferTargetTableSelect.appendChild(option);
            return;
        }

        const emptyTableCards = getEmptyTableCardsForTransfer();

        if (emptyTableCards.length === 0) {
            transferTargetTableSelect.disabled = true;
            transferTableButton.disabled = true;

            const option = document.createElement("option");
            option.value = "";
            option.textContent = "Boş hedef masa yok";
            transferTargetTableSelect.appendChild(option);
            return;
        }

        const placeholderOption = document.createElement("option");
        placeholderOption.value = "";
        placeholderOption.textContent = "Hedef boş masa seçin";
        transferTargetTableSelect.appendChild(placeholderOption);

        emptyTableCards.forEach(function (card) {
            const option = document.createElement("option");
            option.value = card.dataset.tableId;
            option.textContent = `${card.dataset.code} · ${card.dataset.areaName} · ${card.dataset.capacity} kişilik`;
            transferTargetTableSelect.appendChild(option);
        });

        transferTargetTableSelect.disabled = false;
        transferTableButton.disabled = true;
    }

    function resetSelectedTableView() {
        selectedTable = null;

        tableCards.forEach(function (tableCard) {
            tableCard.classList.remove("is-selected");
        });

        selectedTableCode.textContent = "-";
        selectedTableDescription.textContent = "Henüz masa seçilmedi";
        selectedTableStatus.textContent = "Bekliyor";
        selectedTableDuration.textContent = "Soldan bir masa seçin.";

        clearStatusClasses(selectedTableCode);
        clearStatusClasses(selectedTableStatus);
        selectedTableStatus.classList.add("status-neutral");

        assignButton.disabled = true;
        assignButton.textContent = "Önce Boş Masa Seç";

        clearTableButton.disabled = true;

        clearCustomerForm();
        clearActiveCustomerInfo();
        updateSelectedServiceRequestBox();
        updateSelectedReservationBox();
        updateTransferPanel();
        showIdlePanel();
        closeMobileActionPanel();
    }

    function resetSelectedTableIfHidden() {
        if (!selectedTable) {
            return;
        }

        const selectedCard = tableCards.find(function (card) {
            return card.dataset.tableId === selectedTable.id;
        });

        if (!selectedCard || selectedCard.classList.contains("is-hidden")) {
            resetSelectedTableView();
        }
    }

    function selectTable(card) {
        selectedTable = {
            id: card.dataset.tableId,
            code: card.dataset.code,
            areaKey: card.dataset.areaKey,
            areaName: card.dataset.areaName,
            capacity: card.dataset.capacity,
            status: card.dataset.status,
            statusLabel: card.dataset.statusLabel,
            duration: card.dataset.duration,
            partySize: card.dataset.partySize,
            customerName: card.dataset.customerName,
            customerPhone: card.dataset.customerPhone,
            note: card.dataset.note,
            checkInDisplay: card.dataset.checkInDisplay,
            serviceRequestCount: card.dataset.serviceRequestCount || "0",
            serviceRequestLabel: card.dataset.serviceRequestLabel || "",
            serviceRequestStatus: card.dataset.serviceRequestStatus || "",
            reservationHas: card.dataset.reservationHas || "0",
            reservationId: card.dataset.reservationId || "",
            reservationState: card.dataset.reservationState || "",
            reservationStateLabel: card.dataset.reservationStateLabel || "",
            reservationBadgeLabel: card.dataset.reservationBadgeLabel || "",
            reservationTimeLabel: card.dataset.reservationTimeLabel || "",
            reservationDisplay: card.dataset.reservationDisplay || "",
            reservationDateValue: card.dataset.reservationDateValue || "",
            reservationTimeValue: card.dataset.reservationTimeValue || "",
            reservationDurationMinutes: card.dataset.reservationDurationMinutes || "180",
            reservationCustomerName: card.dataset.reservationCustomerName || "",
            reservationCustomerPhone: card.dataset.reservationCustomerPhone || "",
            reservationPartySize: card.dataset.reservationPartySize || "",
            reservationDepositDisplay: card.dataset.reservationDepositDisplay || "",
            reservationDepositAmountValue: card.dataset.reservationDepositAmountValue || "",
            reservationDepositNote: card.dataset.reservationDepositNote || "",
            reservationNote: card.dataset.reservationNote || "",
            reservationProtectionMinutes: card.dataset.reservationProtectionMinutes || "",
            reservationNoShowToleranceMinutes: card.dataset.reservationNoShowToleranceMinutes || "",
            reservationBlocksAssignment: card.dataset.reservationBlocksAssignment || "0",
        };

        tableCards.forEach(function (tableCard) {
            tableCard.classList.remove("is-selected");
        });

        card.classList.add("is-selected");

        selectedTableCode.textContent = selectedTable.code;
        selectedTableDescription.textContent = `${selectedTable.capacity} kişilik · ${selectedTable.areaName}`;
        selectedTableStatus.textContent = selectedTable.statusLabel;

        clearStatusClasses(selectedTableCode);
        clearStatusClasses(selectedTableStatus);

        selectedTableCode.classList.add(getStatusClass(selectedTable.status));
        selectedTableStatus.classList.add(getStatusClass(selectedTable.status));
        updateSelectedReservationBox();

        if (selectedTable.status === "empty") {
            if (selectedTable.reservationBlocksAssignment === "1") {
                selectedTableDuration.textContent = `Bu masa ${selectedTable.reservationTimeLabel || "yaklaşan"} rezervasyonu için korunuyor.`;
            } else if (selectedTable.reservationHas === "1") {
                selectedTableDuration.textContent = `Bu masa boş. ${selectedTable.reservationTimeLabel} için rezervasyon bilgisi var.`;
            } else {
                selectedTableDuration.textContent = "Bu masa boş. Müşteri girişi yapılabilir.";
            }

            updatePersonCount(personCountInput.value || 4);
            clearCustomerForm();
            clearActiveCustomerInfo();

            if (selectedTable.reservationBlocksAssignment === "1") {
                assignButton.disabled = true;
                assignButton.textContent = "Rezervasyon Korumasında";
            } else {
                assignButton.disabled = false;
                assignButton.textContent = "Masaya Gönder";
            }

            clearTableButton.disabled = true;

            updateSelectedServiceRequestBox();
            updateTransferPanel();
            showEmptyTablePanel();
            openMobileActionPanel();
            return;
        }

        if (selectedTable.status === "occupied" || selectedTable.status === "long") {
            selectedTableDuration.textContent = `Masada kalma süresi: ${selectedTable.duration}`;

            assignButton.disabled = true;
            assignButton.textContent = "Sadece Boş Masaya Atama Yapılır";

            clearTableButton.disabled = false;

            clearCustomerForm();
            fillActiveCustomerInfo();
            updateSelectedServiceRequestBox();
            updateTransferPanel();
            showActiveTablePanel();
            openMobileActionPanel();
            return;
        }

        selectedTableDuration.textContent = "Bu masa pasif durumda. İşlem yapılamaz.";

        assignButton.disabled = true;
        assignButton.textContent = "Önce Boş Masa Seç";

        clearTableButton.disabled = true;

        clearCustomerForm();
        clearActiveCustomerInfo();
        updateSelectedServiceRequestBox();
        updateTransferPanel();
        showInactiveTablePanel();
        openMobileActionPanel();
    }

    function setActiveArea(button) {
        activeAreaKey = button.dataset.areaKey;
        activeAreaName = button.querySelector(".area-filter-title").textContent.trim();

        areaButtons.forEach(function (areaButton) {
            areaButton.classList.remove("is-active");
        });

        button.classList.add("is-active");

        if (activeAreaKey === "all") {
            tablePanelTitle.textContent = "Tüm Masalar";
        } else {
            tablePanelTitle.textContent = `${activeAreaName} Masaları`;
        }

        applyFilters();
    }

    function applyFilters() {
        const searchValue = tableSearchInput.value.trim().toLowerCase();
        const statusValue = statusFilter.value;

        let visibleCount = 0;

        tableCards.forEach(function (card) {
            const code = card.dataset.code.toLowerCase();
            const areaKey = card.dataset.areaKey;
            const status = card.dataset.status;

            const searchMatches = searchValue === "" || code.includes(searchValue);
            const areaMatches = activeAreaKey === "all" || areaKey === activeAreaKey;
            const statusMatches = statusValue === "all" || status === statusValue;

            const isVisible = searchMatches && areaMatches && statusMatches;

            if (isVisible) {
                card.classList.remove("is-hidden");
                visibleCount += 1;
            } else {
                card.classList.add("is-hidden");
            }
        });

        visibleTableCount.textContent = `${visibleCount} masa gösteriliyor`;
        resetSelectedTableIfHidden();
    }

    function clearFilters() {
        tableSearchInput.value = "";
        statusFilter.value = "all";

        const allAreaButton = areaButtons.find(function (button) {
            return button.dataset.areaKey === "all";
        });

        if (allAreaButton) {
            setActiveArea(allAreaButton);
        } else {
            activeAreaKey = "all";
            activeAreaName = "Tüm Masalar";
            applyFilters();
        }
    }

    function updatePersonCount(newValue) {
        let parsedValue = Number.parseInt(newValue, 10);

        if (Number.isNaN(parsedValue)) {
            parsedValue = 1;
        }

        if (parsedValue < 1) {
            parsedValue = 1;
        }

        if (parsedValue > 50) {
            parsedValue = 50;
        }

        personCountInput.value = parsedValue;
    }


    function getSelectedTableCard() {
        if (!selectedTable) {
            return null;
        }

        return tableCards.find(function (card) {
            return card.dataset.tableId === selectedTable.id;
        }) || null;
    }

    function highlightSelectedTableForWarning() {
        const selectedCard = getSelectedTableCard();

        if (!selectedCard) {
            return;
        }

        selectedCard.classList.remove("reservation-warning-highlight");
        void selectedCard.offsetWidth;
        selectedCard.classList.add("reservation-warning-highlight");

        window.setTimeout(function () {
            selectedCard.classList.remove("reservation-warning-highlight");
        }, 2600);
    }

    function splitWarningMessage(message) {
        const cleanedMessage = valueOrDash(message)
            .replace(/\r/g, "")
            .trim();

        if (cleanedMessage === "-") {
            return ["İşlem sırasında beklenmeyen bir uyarı oluştu."];
        }

        return cleanedMessage
            .split(/\n|(?<=\.)\s+(?=[A-ZÇĞİÖŞÜ0-9])/g)
            .map(function (line) {
                return line.trim();
            })
            .filter(function (line) {
                return line !== "";
            });
    }

    function getWarningKind(message) {
        const lowerMessage = String(message || "").toLocaleLowerCase("tr-TR");

        if (lowerMessage.includes("rezervasyon") || lowerMessage.includes("koruma")) {
            return "reservation";
        }

        if (lowerMessage.includes("sil") || lowerMessage.includes("pasif") || lowerMessage.includes("hata")) {
            return "danger";
        }

        return "warning";
    }

    function ensureProfessionalWarningModal() {
        let overlay = document.getElementById("professionalWarningOverlay");

        if (overlay) {
            return overlay;
        }

        overlay = document.createElement("div");
        overlay.id = "professionalWarningOverlay";
        overlay.className = "professional-warning-overlay";
        overlay.setAttribute("aria-hidden", "true");

        overlay.innerHTML = `
            <div class="professional-warning-dialog" role="dialog" aria-modal="true" aria-labelledby="professionalWarningTitle">
                <div class="professional-warning-header">
                    <div class="professional-warning-icon" data-warning-icon>⚠</div>
                    <div>
                        <span class="professional-warning-eyebrow" data-warning-eyebrow>Operasyon Uyarısı</span>
                        <h3 id="professionalWarningTitle" data-warning-title>İşlem Uyarısı</h3>
                    </div>
                </div>
                <div class="professional-warning-body" data-warning-body></div>
                <div class="professional-warning-footer">
                    <button type="button" class="professional-warning-button" data-warning-close>Tamam</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeButton = overlay.querySelector("[data-warning-close]");

        closeButton.addEventListener("click", function () {
            closeProfessionalWarningModal();
        });

        overlay.addEventListener("click", function (event) {
            if (event.target === overlay) {
                closeProfessionalWarningModal();
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && overlay.classList.contains("is-visible")) {
                closeProfessionalWarningModal();
            }
        });

        return overlay;
    }

    function closeProfessionalWarningModal() {
        const overlay = document.getElementById("professionalWarningOverlay");

        if (!overlay) {
            return;
        }

        overlay.classList.remove("is-visible");
        overlay.setAttribute("aria-hidden", "true");
    }

    function showProfessionalWarning(message, options) {
        const overlay = ensureProfessionalWarningModal();
        const dialog = overlay.querySelector(".professional-warning-dialog");
        const icon = overlay.querySelector("[data-warning-icon]");
        const eyebrow = overlay.querySelector("[data-warning-eyebrow]");
        const title = overlay.querySelector("[data-warning-title]");
        const body = overlay.querySelector("[data-warning-body]");
        const closeButton = overlay.querySelector("[data-warning-close]");

        const warningKind = options && options.kind ? options.kind : getWarningKind(message);
        const lines = splitWarningMessage(message);

        dialog.classList.remove(
            "professional-warning-reservation",
            "professional-warning-danger",
            "professional-warning-standard"
        );

        if (warningKind === "reservation") {
            dialog.classList.add("professional-warning-reservation");
            icon.textContent = "📅";
            eyebrow.textContent = "Rezervasyon Koruması";
            title.textContent = "Bu Masa Rezervasyon İçin Korunuyor";
        } else if (warningKind === "danger") {
            dialog.classList.add("professional-warning-danger");
            icon.textContent = "⚠";
            eyebrow.textContent = "Dikkat Gerektiren İşlem";
            title.textContent = "İşlem Tamamlanamadı";
        } else {
            dialog.classList.add("professional-warning-standard");
            icon.textContent = "⚠";
            eyebrow.textContent = "Operasyon Uyarısı";
            title.textContent = "İşlem Uyarısı";
        }

        body.innerHTML = "";

        lines.forEach(function (line, index) {
            const paragraph = document.createElement("p");
            paragraph.textContent = line;

            if (index === 0) {
                paragraph.className = "professional-warning-main-text";
            }

            body.appendChild(paragraph);
        });

        if (warningKind === "reservation") {
            const infoBox = document.createElement("div");
            infoBox.className = "professional-warning-info-box";
            infoBox.textContent = "Bu masa, yaklaşan rezervasyon nedeniyle yeni müşteri atamasına kapatılmıştır.";
            body.appendChild(infoBox);
        }

        overlay.classList.add("is-visible");
        overlay.setAttribute("aria-hidden", "false");

        window.setTimeout(function () {
            closeButton.focus();
        }, 50);
    }


    function getReservationTableOptionsHtml(selectedTableId) {
        const sourceSelect = document.querySelector("#reservationModal select[name='table_id']");

        if (!sourceSelect) {
            return "<option value=\"\">Masa listesi bulunamadı</option>";
        }

        return Array.from(sourceSelect.options).map(function (option) {
            const value = option.value || "";
            const selected = String(value) === String(selectedTableId || "") ? " selected" : "";
            const disabled = option.disabled ? " disabled" : "";
            return `<option value="${escapeHtml(value)}"${selected}${disabled}>${escapeHtml(option.textContent.trim())}</option>`;
        }).join("");
    }

    function escapeHtml(value) {
        return String(value === null || value === undefined ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function ensureReservationEditModal() {
        let overlay = document.getElementById("reservationEditOverlay");

        if (overlay) {
            return overlay;
        }

        overlay = document.createElement("div");
        overlay.id = "reservationEditOverlay";
        overlay.className = "reservation-edit-overlay";
        overlay.setAttribute("aria-hidden", "true");

        overlay.innerHTML = `
            <div class="reservation-edit-dialog" role="dialog" aria-modal="true" aria-labelledby="reservationEditTitle">
                <div class="reservation-edit-header">
                    <div class="reservation-edit-icon">📅</div>
                    <div>
                        <span>Yönetici İşlemi</span>
                        <h3 id="reservationEditTitle">Rezervasyonu Düzenle</h3>
                    </div>
                </div>

                <div class="reservation-edit-body">
                    <p id="reservationEditSummary">Seçili rezervasyon güncellenecek.</p>
                    <div class="reservation-edit-info" id="reservationEditInfo"></div>

                    <div class="reservation-edit-grid">
                        <div>
                            <label for="reservationEditDateInput">Tarih *</label>
                            <input id="reservationEditDateInput" type="date" required>
                        </div>
                        <div>
                            <label for="reservationEditTimeInput">Saat *</label>
                            <input id="reservationEditTimeInput" type="time" required>
                        </div>
                        <div>
                            <label for="reservationEditPartyInput">Kişi Sayısı *</label>
                            <input id="reservationEditPartyInput" type="number" min="1" max="50" required>
                        </div>
                        <div>
                            <label for="reservationEditTableSelect">Masa *</label>
                            <select id="reservationEditTableSelect" required></select>
                        </div>
                        <div>
                            <label for="reservationEditCustomerInput">Müşteri Adı</label>
                            <input id="reservationEditCustomerInput" type="text" maxlength="120" placeholder="Ad Soyad">
                        </div>
                        <div>
                            <label for="reservationEditPhoneInput">Telefon *</label>
                            <input id="reservationEditPhoneInput" type="tel" maxlength="40" placeholder="05338463131" required>
                        </div>
                        <div>
                            <label for="reservationEditDepositInput">Kapora Tutarı TL</label>
                            <input id="reservationEditDepositInput" type="text" placeholder="Örn: 3000" inputmode="decimal">
                        </div>
                        <div>
                            <label for="reservationEditDepositNoteInput">Kapora Notu</label>
                            <input id="reservationEditDepositNoteInput" type="text" maxlength="255" placeholder="Nakit / IBAN / açıklama">
                        </div>
                    </div>

                    <label for="reservationEditNoteInput" class="reservation-edit-note-label">Rezervasyon Notu</label>
                    <textarea id="reservationEditNoteInput" rows="3" placeholder="Sahneye yakın masa, doğum günü, özel istek vb."></textarea>

                    <small>Tarih, saat veya masa değişirse çakışma kontrolü yeniden yapılır.</small>
                </div>

                <div class="reservation-edit-footer">
                    <button type="button" class="reservation-edit-secondary" data-reservation-edit-close>Vazgeç</button>
                    <button type="button" class="reservation-edit-primary" data-reservation-edit-confirm>Değişiklikleri Kaydet</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeButtons = Array.from(overlay.querySelectorAll("[data-reservation-edit-close]"));
        closeButtons.forEach(function (button) {
            button.addEventListener("click", closeReservationEditModal);
        });

        const confirmButton = overlay.querySelector("[data-reservation-edit-confirm]");
        if (confirmButton) {
            confirmButton.addEventListener("click", handleReservationEditSubmit);
        }

        overlay.addEventListener("click", function (event) {
            if (event.target === overlay) {
                closeReservationEditModal();
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && overlay.classList.contains("is-visible")) {
                closeReservationEditModal();
            }
        });

        return overlay;
    }

    function openReservationEditModal() {
        if (!selectedTable || selectedTable.reservationHas !== "1" || !selectedTable.reservationId) {
            showProfessionalWarning("Düzenlenecek aktif rezervasyon bulunamadı.");
            return;
        }

        const overlay = ensureReservationEditModal();
        const summary = overlay.querySelector("#reservationEditSummary");
        const info = overlay.querySelector("#reservationEditInfo");
        const tableSelect = overlay.querySelector("#reservationEditTableSelect");
        const dateInput = overlay.querySelector("#reservationEditDateInput");
        const timeInput = overlay.querySelector("#reservationEditTimeInput");
        const partyInput = overlay.querySelector("#reservationEditPartyInput");
        const customerInput = overlay.querySelector("#reservationEditCustomerInput");
        const phoneInput = overlay.querySelector("#reservationEditPhoneInput");
        const depositInput = overlay.querySelector("#reservationEditDepositInput");
        const depositNoteInput = overlay.querySelector("#reservationEditDepositNoteInput");
        const noteInput = overlay.querySelector("#reservationEditNoteInput");
        const confirmButton = overlay.querySelector("[data-reservation-edit-confirm]");

        if (summary) {
            summary.textContent = `${selectedTable.code} masasına ait rezervasyon düzenlenecek.`;
        }

        if (info) {
            info.innerHTML = `
                <div><span>Mevcut Masa</span><strong>${valueOrDash(selectedTable.code)}</strong></div>
                <div><span>Mevcut Tarih / Saat</span><strong>${valueOrDash(selectedTable.reservationDisplay)}</strong></div>
                <div><span>Müşteri</span><strong>${valueOrDash(selectedTable.reservationCustomerName)}</strong></div>
                <div><span>Telefon</span><strong>${valueOrDash(selectedTable.reservationCustomerPhone)}</strong></div>
            `;
        }

        if (tableSelect) {
            tableSelect.innerHTML = getReservationTableOptionsHtml(selectedTable.id);
            tableSelect.value = selectedTable.id || "";
        }

        if (dateInput) {
            dateInput.value = selectedTable.reservationDateValue || "";
        }

        if (timeInput) {
            timeInput.value = selectedTable.reservationTimeValue || "";
        }

        if (partyInput) {
            partyInput.value = selectedTable.reservationPartySize || "";
        }

        if (customerInput) {
            customerInput.value = selectedTable.reservationCustomerName === "İsimsiz müşteri" ? "" : (selectedTable.reservationCustomerName || "");
        }

        if (phoneInput) {
            phoneInput.value = selectedTable.reservationCustomerPhone || "";
        }

        if (depositInput) {
            depositInput.value = selectedTable.reservationDepositAmountValue || "";
        }

        if (depositNoteInput) {
            depositNoteInput.value = selectedTable.reservationDepositNote || "";
        }

        if (noteInput) {
            noteInput.value = selectedTable.reservationNote || "";
        }

        if (confirmButton) {
            confirmButton.disabled = false;
            confirmButton.textContent = "Değişiklikleri Kaydet";
        }

        overlay.classList.add("is-visible");
        overlay.setAttribute("aria-hidden", "false");

        window.setTimeout(function () {
            if (dateInput) {
                dateInput.focus();
            }
        }, 50);
    }

    function closeReservationEditModal() {
        const overlay = document.getElementById("reservationEditOverlay");

        if (!overlay) {
            return;
        }

        overlay.classList.remove("is-visible");
        overlay.setAttribute("aria-hidden", "true");
    }

    function readReservationEditPayload(overlay) {
        const dateInput = overlay.querySelector("#reservationEditDateInput");
        const timeInput = overlay.querySelector("#reservationEditTimeInput");
        const partyInput = overlay.querySelector("#reservationEditPartyInput");
        const tableSelect = overlay.querySelector("#reservationEditTableSelect");
        const customerInput = overlay.querySelector("#reservationEditCustomerInput");
        const phoneInput = overlay.querySelector("#reservationEditPhoneInput");
        const depositInput = overlay.querySelector("#reservationEditDepositInput");
        const depositNoteInput = overlay.querySelector("#reservationEditDepositNoteInput");
        const noteInput = overlay.querySelector("#reservationEditNoteInput");

        return {
            table_id: tableSelect ? tableSelect.value : "",
            reservation_date: dateInput ? dateInput.value : "",
            reservation_time: timeInput ? timeInput.value : "",
            party_size: partyInput ? partyInput.value : "",
            customer_name: customerInput ? customerInput.value : "",
            customer_phone: phoneInput ? phoneInput.value : "",
            deposit_amount_tl: depositInput ? depositInput.value : "",
            deposit_note: depositNoteInput ? depositNoteInput.value : "",
            note: noteInput ? noteInput.value : "",
            duration_minutes: selectedTable ? selectedTable.reservationDurationMinutes : "180",
            protection_minutes: selectedTable ? selectedTable.reservationProtectionMinutes : "45",
            no_show_tolerance_minutes: selectedTable ? selectedTable.reservationNoShowToleranceMinutes : "30",
        };
    }

    function validateReservationEditPayload(payload) {
        if (!payload.reservation_date) {
            throw new Error("Rezervasyon tarihi zorunludur.");
        }

        if (!payload.reservation_time) {
            throw new Error("Rezervasyon saati zorunludur.");
        }

        if (!payload.table_id) {
            throw new Error("Masa seçimi zorunludur.");
        }

        if (!payload.party_size) {
            throw new Error("Kişi sayısı zorunludur.");
        }

        if (!payload.customer_phone || String(payload.customer_phone).trim() === "") {
            throw new Error("Telefon zorunludur.");
        }
    }

    async function handleReservationEditSubmit() {
        if (!selectedTable || !selectedTable.reservationId) {
            showProfessionalWarning("Düzenlenecek aktif rezervasyon bulunamadı.");
            return;
        }

        const overlay = ensureReservationEditModal();
        const confirmButton = overlay.querySelector("[data-reservation-edit-confirm]");
        const normalText = "Değişiklikleri Kaydet";

        let payload = null;

        try {
            payload = readReservationEditPayload(overlay);
            validateReservationEditPayload(payload);
        } catch (error) {
            showProfessionalWarning(error.message, { kind: "warning" });
            return;
        }

        if (confirmButton) {
            confirmButton.disabled = true;
            confirmButton.textContent = "Kaydediliyor...";
        }

        try {
            await postJson(`/api/reservations/${selectedTable.reservationId}/update`, payload);
            window.location.reload();
        } catch (error) {
            showProfessionalWarning(error.message, { kind: "danger" });
            highlightSelectedTableForWarning();

            if (confirmButton) {
                confirmButton.disabled = false;
                confirmButton.textContent = normalText;
            }
        }
    }


    function ensureReservationCancelModal() {
        let overlay = document.getElementById("reservationCancelOverlay");

        if (overlay) {
            return overlay;
        }

        overlay = document.createElement("div");
        overlay.id = "reservationCancelOverlay";
        overlay.className = "reservation-cancel-overlay";
        overlay.setAttribute("aria-hidden", "true");

        overlay.innerHTML = `
            <div class="reservation-cancel-dialog" role="dialog" aria-modal="true" aria-labelledby="reservationCancelTitle">
                <div class="reservation-cancel-header">
                    <div class="reservation-cancel-icon">📅</div>
                    <div>
                        <span>Yönetici İşlemi</span>
                        <h3 id="reservationCancelTitle">Rezervasyonu İptal Et</h3>
                    </div>
                </div>

                <div class="reservation-cancel-body">
                    <p id="reservationCancelSummary">Seçili rezervasyon iptal edilecek.</p>
                    <div class="reservation-cancel-info" id="reservationCancelInfo"></div>

                    <label for="reservationCancelReasonInput">İptal sebebi</label>
                    <textarea
                        id="reservationCancelReasonInput"
                        rows="3"
                        placeholder="Örn: Müşteri arayıp iptal etti, kapora iade edildi..."
                    ></textarea>
                    <small>Bu bilgi işlem loguna kaydedilir. Boş bırakabilirsiniz.</small>
                </div>

                <div class="reservation-cancel-footer">
                    <button type="button" class="reservation-cancel-secondary" data-reservation-cancel-close>Vazgeç</button>
                    <button type="button" class="reservation-cancel-danger" data-reservation-cancel-confirm>Rezervasyonu İptal Et</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeButtons = Array.from(overlay.querySelectorAll("[data-reservation-cancel-close]"));
        closeButtons.forEach(function (button) {
            button.addEventListener("click", closeReservationCancelModal);
        });

        const confirmButton = overlay.querySelector("[data-reservation-cancel-confirm]");
        if (confirmButton) {
            confirmButton.addEventListener("click", handleReservationCancelSubmit);
        }

        overlay.addEventListener("click", function (event) {
            if (event.target === overlay) {
                closeReservationCancelModal();
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && overlay.classList.contains("is-visible")) {
                closeReservationCancelModal();
            }
        });

        return overlay;
    }

    function openReservationCancelModal() {
        if (!selectedTable || selectedTable.reservationHas !== "1" || !selectedTable.reservationId) {
            showProfessionalWarning("İptal edilecek aktif rezervasyon bulunamadı.");
            return;
        }

        const overlay = ensureReservationCancelModal();
        const summary = overlay.querySelector("#reservationCancelSummary");
        const info = overlay.querySelector("#reservationCancelInfo");
        const reasonInput = overlay.querySelector("#reservationCancelReasonInput");
        const confirmButton = overlay.querySelector("[data-reservation-cancel-confirm]");

        if (summary) {
            summary.textContent = `${selectedTable.code} masasına ait rezervasyon iptal edilecek.`;
        }

        if (info) {
            info.innerHTML = `
                <div><span>Masa</span><strong>${valueOrDash(selectedTable.code)}</strong></div>
                <div><span>Tarih / Saat</span><strong>${valueOrDash(selectedTable.reservationDisplay)}</strong></div>
                <div><span>Müşteri</span><strong>${valueOrDash(selectedTable.reservationCustomerName)}</strong></div>
                <div><span>Telefon</span><strong>${valueOrDash(selectedTable.reservationCustomerPhone)}</strong></div>
                <div><span>Kişi</span><strong>${valueOrDash(selectedTable.reservationPartySize)} kişi</strong></div>
                <div><span>Kapora</span><strong>${valueOrDash(selectedTable.reservationDepositDisplay)}</strong></div>
            `;
        }

        if (reasonInput) {
            reasonInput.value = "";
        }

        if (confirmButton) {
            confirmButton.disabled = false;
            confirmButton.textContent = "Rezervasyonu İptal Et";
        }

        overlay.classList.add("is-visible");
        overlay.setAttribute("aria-hidden", "false");

        window.setTimeout(function () {
            if (reasonInput) {
                reasonInput.focus();
            }
        }, 50);
    }

    function closeReservationCancelModal() {
        const overlay = document.getElementById("reservationCancelOverlay");

        if (!overlay) {
            return;
        }

        overlay.classList.remove("is-visible");
        overlay.setAttribute("aria-hidden", "true");
    }

    async function handleReservationCancelSubmit() {
        if (!selectedTable || !selectedTable.reservationId) {
            showProfessionalWarning("İptal edilecek aktif rezervasyon bulunamadı.");
            return;
        }

        const overlay = ensureReservationCancelModal();
        const reasonInput = overlay.querySelector("#reservationCancelReasonInput");
        const confirmButton = overlay.querySelector("[data-reservation-cancel-confirm]");
        const normalText = "Rezervasyonu İptal Et";

        if (confirmButton) {
            confirmButton.disabled = true;
            confirmButton.textContent = "İptal ediliyor...";
        }

        try {
            await postJson(`/api/reservations/${selectedTable.reservationId}/cancel`, {
                cancel_reason: reasonInput ? reasonInput.value : "",
            });

            window.location.reload();
        } catch (error) {
            showProfessionalWarning(error.message, { kind: "danger" });
            highlightSelectedTableForWarning();

            if (confirmButton) {
                confirmButton.disabled = false;
                confirmButton.textContent = normalText;
            }
        }
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(payload),
        });

        const responseText = await response.text();
        let data = null;

        if (responseText) {
            try {
                data = JSON.parse(responseText);
            } catch (parseError) {
                const cleanPreview = responseText
                    .replace(/<[^>]*>/g, " ")
                    .replace(/\s+/g, " ")
                    .trim()
                    .slice(0, 220);

                if (!response.ok) {
                    throw new Error(
                        cleanPreview ||
                        "Sunucu işlem sırasında HTML hata sayfası döndürdü. Terminaldeki kırmızı hata metnini kontrol edin."
                    );
                }

                throw new Error("Sunucu JSON formatında cevap döndürmedi.");
            }
        }

        if (!response.ok || !data || !data.success) {
            throw new Error(
                data && data.message
                    ? data.message
                    : "İşlem sırasında hata oluştu."
            );
        }

        return data;
    }

    tableCards.forEach(function (card) {
        card.addEventListener("click", function () {
            selectTable(card);
        });
    });

    areaButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            setActiveArea(button);
        });
    });

    tableSearchInput.addEventListener("input", applyFilters);
    statusFilter.addEventListener("change", applyFilters);
    clearFiltersButton.addEventListener("click", clearFilters);

    decreasePersonButton.addEventListener("click", function () {
        const currentValue = Number.parseInt(personCountInput.value, 10) || 1;
        updatePersonCount(currentValue - 1);
    });

    increasePersonButton.addEventListener("click", function () {
        const currentValue = Number.parseInt(personCountInput.value, 10) || 1;
        updatePersonCount(currentValue + 1);
    });

    personCountInput.addEventListener("input", function () {
        updatePersonCount(personCountInput.value);
    });

    if (editReservationButton) {
        editReservationButton.addEventListener("click", function () {
            openReservationEditModal();
        });
    }

    if (cancelReservationButton) {
        cancelReservationButton.addEventListener("click", function () {
            openReservationCancelModal();
        });
    }

    transferTargetTableSelect.addEventListener("change", function () {
        if (!selectedTable || (selectedTable.status !== "occupied" && selectedTable.status !== "long")) {
            transferTableButton.disabled = true;
            return;
        }

        transferTableButton.disabled = transferTargetTableSelect.value === "";
    });

    assignButton.addEventListener("click", async function () {
        if (!selectedTable || selectedTable.status !== "empty") {
            return;
        }

        const normalText = "Masaya Gönder";
        setButtonLoading(assignButton, true, "Kaydediliyor...", normalText);

        try {
            await postJson("/api/tables/assign", {
                table_id: selectedTable.id,
                party_size: personCountInput.value,
                customer_name: customerNameInput.value,
                customer_phone: customerPhoneInput.value,
                note: customerNoteInput.value,
            });

            window.location.reload();
        } catch (error) {
            showProfessionalWarning(error.message);
            highlightSelectedTableForWarning();
            assignButton.disabled = false;
            assignButton.textContent = normalText;
        }
    });

    clearTableButton.addEventListener("click", async function () {
        if (!selectedTable || (selectedTable.status !== "occupied" && selectedTable.status !== "long")) {
            return;
        }

        const confirmed = confirm(`${selectedTable.code} masası boşaltılacak. Onaylıyor musunuz?`);

        if (!confirmed) {
            return;
        }

        const normalText = "Masa Boşaldı";
        setButtonLoading(clearTableButton, true, "Boşaltılıyor...", normalText);

        try {
            await postJson("/api/tables/clear", {
                table_id: selectedTable.id,
            });

            window.location.reload();
        } catch (error) {
            showProfessionalWarning(error.message);
            highlightSelectedTableForWarning();
            clearTableButton.disabled = false;
            clearTableButton.textContent = normalText;
        }
    });

    transferTableButton.addEventListener("click", async function () {
        if (!selectedTable || (selectedTable.status !== "occupied" && selectedTable.status !== "long")) {
            return;
        }

        const targetTableId = transferTargetTableSelect.value;

        if (!targetTableId) {
            showProfessionalWarning("Lütfen hedef boş masa seçin.");
            return;
        }

        const selectedTargetOption = transferTargetTableSelect.options[transferTargetTableSelect.selectedIndex];
        const confirmed = confirm(
            `${selectedTable.code} masasındaki müşteri ${selectedTargetOption.textContent} masasına transfer edilecek. Onaylıyor musunuz?`
        );

        if (!confirmed) {
            return;
        }

        const normalText = "Masayı Transfer Et";
        setButtonLoading(transferTableButton, true, "Transfer ediliyor...", normalText);

        try {
            await postJson("/api/tables/transfer", {
                source_table_id: selectedTable.id,
                target_table_id: targetTableId,
            });

            window.location.reload();
        } catch (error) {
            showProfessionalWarning(error.message);
            highlightSelectedTableForWarning();
            transferTableButton.disabled = false;
            transferTableButton.textContent = normalText;
        }
    });

    if (mobilePanelCloseButton) {
        mobilePanelCloseButton.addEventListener("click", closeMobileActionPanel);
    }

    if (mobilePanelBackdrop) {
        mobilePanelBackdrop.addEventListener("click", closeMobileActionPanel);
    }

    window.addEventListener("resize", handleViewportChange);

    initializeOccupancyBars();
    applyFilters();
    resetSelectedTableView();
});