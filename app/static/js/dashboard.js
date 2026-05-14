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

    const selectedTableCode = document.getElementById("selectedTableCode");
    const selectedTableDescription = document.getElementById("selectedTableDescription");
    const selectedTableStatus = document.getElementById("selectedTableStatus");
    const selectedTableDuration = document.getElementById("selectedTableDuration");

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

    const transferTargetTableSelect = document.getElementById("transferTargetTableSelect");
    const transferTableButton = document.getElementById("transferTableButton");

    let selectedTable = null;
    let activeAreaKey = "all";
    let activeAreaName = "Tüm Masalar";

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
        updateTransferPanel();
        showIdlePanel();
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

        if (selectedTable.status === "empty") {
            selectedTableDuration.textContent = "Bu masa boş. Müşteri girişi yapılabilir.";

            updatePersonCount(personCountInput.value || 4);
            clearCustomerForm();
            clearActiveCustomerInfo();

            assignButton.disabled = false;
            assignButton.textContent = "Masaya Gönder";

            clearTableButton.disabled = true;

            updateTransferPanel();
            showEmptyTablePanel();
            return;
        }

        if (selectedTable.status === "occupied" || selectedTable.status === "long") {
            selectedTableDuration.textContent = `Masada kalma süresi: ${selectedTable.duration}`;

            assignButton.disabled = true;
            assignButton.textContent = "Sadece Boş Masaya Atama Yapılır";

            clearTableButton.disabled = false;

            clearCustomerForm();
            fillActiveCustomerInfo();
            updateTransferPanel();
            showActiveTablePanel();
            return;
        }

        selectedTableDuration.textContent = "Bu masa pasif durumda. İşlem yapılamaz.";

        assignButton.disabled = true;
        assignButton.textContent = "Önce Boş Masa Seç";

        clearTableButton.disabled = true;

        clearCustomerForm();
        clearActiveCustomerInfo();
        updateTransferPanel();
        showInactiveTablePanel();
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

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || "İşlem sırasında hata oluştu.");
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
            alert(error.message);
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
            alert(error.message);
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
            alert("Lütfen hedef boş masa seçin.");
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
            alert(error.message);
            transferTableButton.disabled = false;
            transferTableButton.textContent = normalText;
        }
    });

    initializeOccupancyBars();
    applyFilters();
    resetSelectedTableView();
});