document.addEventListener("DOMContentLoaded", function () {
    const tableCards = Array.from(document.querySelectorAll("[data-table-card]"));
    const recommendedButtons = Array.from(document.querySelectorAll("[data-recommended-table]"));

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

    const personCountInput = document.getElementById("personCountInput");
    const decreasePersonButton = document.getElementById("decreasePersonButton");
    const increasePersonButton = document.getElementById("increasePersonButton");
    const assignButton = document.getElementById("assignButton");

    const staffSelectedTableCode = document.getElementById("staffSelectedTableCode");
    const staffSelectedTableText = document.getElementById("staffSelectedTableText");
    const clearTableButton = document.getElementById("clearTableButton");

    let selectedTable = null;

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

    function findTableCardByCode(code) {
        return tableCards.find(function (card) {
            return card.dataset.code === code;
        });
    }

    function selectTable(card) {
        selectedTable = {
            code: card.dataset.code,
            areaKey: card.dataset.areaKey,
            areaName: card.dataset.areaName,
            capacity: card.dataset.capacity,
            status: card.dataset.status,
            statusLabel: card.dataset.statusLabel,
            duration: card.dataset.duration,
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
        } else if (selectedTable.status === "empty") {
            selectedTableDuration.textContent = "Bu masa boş. Müşteri ataması yapılabilir.";
        } else {
            selectedTableDuration.textContent = "Bu masa pasif durumda. İşlem yapılamaz.";
        }

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

    tableCards.forEach(function (card) {
        card.addEventListener("click", function () {
            selectTable(card);
        });
    });

    recommendedButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            const tableCode = button.dataset.code;
            const matchingCard = findTableCardByCode(tableCode);

            if (matchingCard) {
                selectTable(matchingCard);
                matchingCard.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                });
            }
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

    assignButton.addEventListener("click", function () {
        if (!selectedTable || selectedTable.status !== "empty") {
            return;
        }

        alert(`${selectedTable.code} masasına ${personCountInput.value} kişi yönlendirilecek. Bu adımda henüz veritabanına kayıt yapılmıyor.`);
    });

    clearTableButton.addEventListener("click", function () {
        if (!selectedTable || (selectedTable.status !== "occupied" && selectedTable.status !== "long")) {
            return;
        }

        alert(`${selectedTable.code} masası boşaltılacak. Bu adımda henüz veritabanına kayıt yapılmıyor.`);
    });

    applyFilters();
});