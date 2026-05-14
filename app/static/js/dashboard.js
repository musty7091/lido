document.addEventListener("DOMContentLoaded", function () {
    const tableCards = Array.from(document.querySelectorAll("[data-table-card]"));
    const occupancyBars = Array.from(document.querySelectorAll("[data-occupancy-rate]"));

    const csrfTokenElement = document.querySelector("meta[name='csrf-token']");
    const csrfToken = csrfTokenElement ? csrfTokenElement.getAttribute("content") : "";

    const tableSearchInput = document.getElementById("tableSearchInput");
    const areaFilter = document.getElementById("areaFilter");
    const capacityFilter = document.getElementById("capacityFilter");
    const statusFilter = document.getElementById("statusFilter");
    const clearFiltersButton = document.getElementById("clearFiltersButton");
    const visibleTableCount = document.getElementById("visibleTableCount");

    const selectedTableCode = document.getElementById("selectedTableCode");
    const selectedTableDescription = document.getElementById("selectedTableDescription");
    const selectedTableStatus = document.getElementById("selectedTableStatus");
    const selectedTableDuration = document.getElementById("selectedTableDuration");

    const selectedCustomerInfo = document.getElementById("selectedCustomerInfo");
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

    const staffSelectedTableCode = document.getElementById("staffSelectedTableCode");
    const staffSelectedTableText = document.getElementById("staffSelectedTableText");
    const clearTableButton = document.getElementById("clearTableButton");

    const transferTargetTableSelect = document.getElementById("transferTargetTableSelect");
    const transferTableButton = document.getElementById("transferTableButton");

    let selectedTable = null;

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

    function clearCustomerForm() {
        customerNameInput.value = "";
        customerPhoneInput.value = "";
        customerNoteInput.value = "";
    }

    function fillCustomerFormFromSelectedTable() {
        customerNameInput.value = selectedTable.customerName || "";
        customerPhoneInput.value = selectedTable.customerPhone || "";
        customerNoteInput.value = selectedTable.note || "";
    }

    function updateSelectedCustomerInfo() {
        const hasActiveCustomer =
            selectedTable &&
            (selectedTable.status === "occupied" || selectedTable.status === "long");

        if (!hasActiveCustomer) {
            selectedCustomerInfo.classList.add("is-passive");
            selectedPartySizeText.textContent = "-";
            selectedCustomerNameText.textContent = "-";
            selectedCustomerPhoneText.textContent = "-";
            selectedCheckInText.textContent = "-";
            selectedCustomerNoteText.textContent = "Bu masa boş. Yeni müşteri bilgisi girilebilir.";
            return;
        }

        selectedCustomerInfo.classList.remove("is-passive");
        selectedPartySizeText.textContent = valueOrDash(selectedTable.partySize);
        selectedCustomerNameText.textContent = valueOrDash(selectedTable.customerName);
        selectedCustomerPhoneText.textContent = valueOrDash(selectedTable.customerPhone);
        selectedCheckInText.textContent = valueOrDash(selectedTable.checkInDisplay);
        selectedCustomerNoteText.textContent = valueOrDash(selectedTable.note);
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

        if (selectedTable.status === "occupied" || selectedTable.status === "long") {
            selectedTableDuration.textContent = `Masada kalma süresi: ${selectedTable.duration}`;

            if (selectedTable.partySize) {
                personCountInput.value = selectedTable.partySize;
            }

            fillCustomerFormFromSelectedTable();
        } else if (selectedTable.status === "empty") {
            selectedTableDuration.textContent = "Bu masa boş. Müşteri ataması yapılabilir.";
            updatePersonCount(personCountInput.value || 4);
            clearCustomerForm();
        } else {
            selectedTableDuration.textContent = "Bu masa pasif durumda. İşlem yapılamaz.";
            clearCustomerForm();
        }

        updateSelectedCustomerInfo();

        staffSelectedTableCode.textContent = selectedTable.code;
        staffSelectedTableText.textContent = `${selectedTable.areaName} · ${selectedTable.statusLabel}`;

        if (selectedTable.status === "empty") {
            assignButton.disabled = false;
            assignButton.textContent = "Masaya Gönder";
        } else {
            assignButton.disabled = true;
            assignButton.textContent = "Sadece Boş Masaya Atama Yapılır";
        }

        if (selectedTable.status === "occupied" || selectedTable.status === "long") {
            clearTableButton.disabled = false;
        } else {
            clearTableButton.disabled = true;
        }

        updateTransferPanel();
    }

    function applyFilters() {
        const searchValue = tableSearchInput.value.trim().toLowerCase();
        const areaValue = areaFilter.value;
        const capacityValue = capacityFilter.value;
        const statusValue = statusFilter.value;

        let visibleCount = 0;

        tableCards.forEach(function (card) {
            const code = card.dataset.code.toLowerCase();
            const areaKey = card.dataset.areaKey;
            const capacity = card.dataset.capacity;
            const status = card.dataset.status;

            const searchMatches = searchValue === "" || code.includes(searchValue);
            const areaMatches = areaValue === "all" || areaKey === areaValue;
            const capacityMatches = capacityValue === "all" || capacity === capacityValue;
            const statusMatches = statusValue === "all" || status === statusValue;

            const isVisible = searchMatches && areaMatches && capacityMatches && statusMatches;

            if (isVisible) {
                card.classList.remove("is-hidden");
                visibleCount += 1;
            } else {
                card.classList.add("is-hidden");
            }
        });

        visibleTableCount.textContent = `${visibleCount} masa gösteriliyor`;
    }

    function clearFilters() {
        tableSearchInput.value = "";
        areaFilter.value = "all";
        capacityFilter.value = "all";
        statusFilter.value = "all";

        applyFilters();
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

    tableSearchInput.addEventListener("input", applyFilters);
    areaFilter.addEventListener("change", applyFilters);
    capacityFilter.addEventListener("change", applyFilters);
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
    updateSelectedCustomerInfo();
    updateTransferPanel();
});