document.addEventListener("DOMContentLoaded", function () {
    const rowsPerPage = 30;
    const table = document.getElementById("performanceTable");
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const totalRows = rows.length;
    const totalPages = Math.ceil(totalRows / rowsPerPage);
    const pagination = document.getElementById("pagination");
    
    // Function to display a given page of rows
    function showPage(page) {
      const startIndex = (page - 1) * rowsPerPage;
      const endIndex = startIndex + rowsPerPage;
      rows.forEach((row, index) => {
        row.style.display = (index >= startIndex && index < endIndex) ? "" : "none";
      });
    }
    
    // Create and update pagination buttons
    function setupPagination() {
      pagination.innerHTML = "";
      let currentPage = 1;
      
      // Prev Button
      const prevButton = document.createElement("button");
      prevButton.innerHTML = "Prev";
      prevButton.className = "pagination-btn";
      prevButton.disabled = true;
      pagination.appendChild(prevButton);
      
      // Page Number Buttons
      for (let i = 1; i <= totalPages; i++) {
        const pageButton = document.createElement("button");
        pageButton.innerHTML = i;
        pageButton.className = "pagination-btn";
        if (i === 1) pageButton.classList.add("active");
        pagination.appendChild(pageButton);
        
        pageButton.addEventListener("click", function () {
          currentPage = i;
          updateButtons();
          showPage(currentPage);
          updateActiveButton();
        });
      }
      
      // Next Button
      const nextButton = document.createElement("button");
      nextButton.innerHTML = "Next";
      nextButton.className = "pagination-btn";
      if (totalPages <= 1) nextButton.disabled = true;
      pagination.appendChild(nextButton);
      
      function updateButtons() {
        prevButton.disabled = currentPage === 1;
        nextButton.disabled = currentPage === totalPages;
      }
      
      function updateActiveButton() {
        const buttons = pagination.querySelectorAll("button");
        buttons.forEach(btn => {
          if (!isNaN(parseInt(btn.innerHTML))) {
            btn.classList.toggle("active", parseInt(btn.innerHTML) === currentPage);
          }
        });
      }
      
      prevButton.addEventListener("click", function () {
        if (currentPage > 1) {
          currentPage--;
          showPage(currentPage);
          updateButtons();
          updateActiveButton();
        }
      });
      
      nextButton.addEventListener("click", function () {
        if (currentPage < totalPages) {
          currentPage++;
          showPage(currentPage);
          updateButtons();
          updateActiveButton();
        }
      });
      
      // Show the first page initially
      showPage(1);
    }
    
    if (totalRows > rowsPerPage) {
      setupPagination();
    }
  });