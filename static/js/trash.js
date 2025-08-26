document.addEventListener("DOMContentLoaded", function() {
    const modal = document.getElementById("trash-custom-model");
    const confirmBtn = document.getElementById("confirm-btn");
    const cancelBtn = document.getElementById("cancel-btn");
    const modalMessage = document.getElementById("modal-message");
  
    let resolveAction;
  
    // Function to show the modal; renamed to trashCustomModel
    function trashCustomModel(message) {
      modalMessage.textContent = message;
      modal.style.display = "flex";
      return new Promise((resolve) => {
        resolveAction = resolve;
      });
    }
  
    // Confirm button event
    confirmBtn.addEventListener("click", function() {
      if (resolveAction) {
        resolveAction(true);
      }
      modal.style.display = "none";
    });
  
    // Cancel button event
    cancelBtn.addEventListener("click", function() {
      if (resolveAction) {
        resolveAction(false);
      }
      modal.style.display = "none";
    });
  
    // Hide modal if clicking outside the modal-content
    modal.addEventListener("click", function(event) {
      if (event.target === modal) {
        if (resolveAction) {
          resolveAction(false);
        }
        modal.style.display = "none";
      }
    });
  
    // Bind click events to trigger-delete buttons
    document.querySelectorAll(".trigger-delete").forEach((button) => {
      button.addEventListener("click", function(event) {
        event.preventDefault();
        const actionUrl = this.getAttribute("data-action");
        // Use trashCustomModel to show the modal confirmation
        trashCustomModel("Are you sure you want to permanently delete this item?")
          .then((confirmed) => {
            if (confirmed) {
              // Create and submit a form to perform deletion
              const form = document.createElement("form");
              form.method = "POST";
              form.action = actionUrl;
              document.body.appendChild(form);
              form.submit();
            }
          });
      });
    });
  });
  