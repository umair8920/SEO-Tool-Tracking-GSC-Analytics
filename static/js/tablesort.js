// static/js/tablesort.js

document.addEventListener("DOMContentLoaded", function () {
    // Find all tables with the class 'sortable'
    const tables = document.querySelectorAll("table.sortable");
  
    tables.forEach((table) => {
      const headers = table.querySelectorAll("thead th");
  
      headers.forEach((header, index) => {
        header.style.cursor = "pointer"; // indicate clickability
  
        header.addEventListener("click", () => {
          // Determine current sort direction and toggle it
          let currentSort = header.getAttribute("data-sort-direction") || "asc";
          let newSort = currentSort === "asc" ? "desc" : "asc";
          header.setAttribute("data-sort-direction", newSort);
  
          sortTableByColumn(table, index, newSort);
        });
      });
    });
  
    /**
     * Sorts a table by a specific column.
     * @param {HTMLTableElement} table The table element.
     * @param {number} columnIndex The index of the column to sort by.
     * @param {string} sortDirection 'asc' or 'desc'
     */
    function sortTableByColumn(table, columnIndex, sortDirection) {
      const tbody = table.querySelector("tbody");
      const rows = Array.from(tbody.querySelectorAll("tr"));
  
      // Sort rows based on the content of the cells in the specified column
      rows.sort((a, b) => {
        const cellA = a.children[columnIndex].textContent.trim();
        const cellB = b.children[columnIndex].textContent.trim();
  
        // Try to convert cell content to numbers if possible
        const numA = parseFloat(cellA.replace(/[^0-9.-]+/g, ""));
        const numB = parseFloat(cellB.replace(/[^0-9.-]+/g, ""));
  
        let valueA, valueB;
  
        if (!isNaN(numA) && !isNaN(numB)) {
          valueA = numA;
          valueB = numB;
        } else {
          valueA = cellA.toLowerCase();
          valueB = cellB.toLowerCase();
        }
  
        if (valueA < valueB) {
          return sortDirection === "asc" ? -1 : 1;
        } else if (valueA > valueB) {
          return sortDirection === "asc" ? 1 : -1;
        } else {
          return 0;
        }
      });
  
      // Re-append sorted rows to the tbody
      rows.forEach((row) => tbody.appendChild(row));
    }
  });
  