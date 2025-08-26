document.addEventListener("DOMContentLoaded", function () {
  let selectedForm = null;

  function openConfirmModal(event, message) {
      event.preventDefault(); // Prevent form submission
      selectedForm = event.target.closest("form");
      document.getElementById("modal-message").textContent = message;
      document.getElementById("confirm-modal").style.display = "block";
      document.getElementById("modal-overlay").style.display = "block";
  }

  function closeConfirmModal() {
      document.getElementById("confirm-modal").style.display = "none";
      document.getElementById("modal-overlay").style.display = "none";
      selectedForm = null;
  }

  function confirmDelete() {
      if (selectedForm) {
          selectedForm.submit();
      }
  }

  // For deleting clusters
  document.querySelectorAll(".delete-btn").forEach((btn) => {
      btn.addEventListener("click", function (event) {
          openConfirmModal(event, "This will move the cluster to trash. You have 30 days to restore it before it is permanently deleted. Continue?");
      });
  });

  // For deleting links
  document.querySelectorAll(".delete-link-btn").forEach((btn) => {
      btn.addEventListener("click", function (event) {
          openConfirmModal(event, "This will move the link to trash. You have 30 days to restore it before it is permanently deleted. Continue?");
      });
  });

  // For refreshing GSC data
  document.querySelectorAll(".refresh-gsc-btn").forEach((btn) => {
      btn.addEventListener("click", function (event) {
          openConfirmModal(event, "Refresh GSC data for this link?");
      });
  });

  document.getElementById("confirm-delete").addEventListener("click", confirmDelete);
  document.getElementById("cancel-delete").addEventListener("click", closeConfirmModal);
  document.getElementById("modal-overlay").addEventListener("click", closeConfirmModal);
});



  
  function showModal(message, type) {
    const modal = document.getElementById('custom-modal');
    const modalMessage = document.getElementById('modal-message');
    const modalContent = modal.querySelector('.modal-content');
  
    modalMessage.textContent = message;
  
    // Remove existing type classes and apply new one.
    modalContent.classList.remove('modal-success', 'modal-danger', 'modal-warning');
    if (type === "success") {
      modalContent.classList.add('modal-success');
    } else if (type === "danger") {
      modalContent.classList.add('modal-danger');
    } else if (type === "warning") {
      modalContent.classList.add('modal-warning');
    }
  
    // Show modal with fade-in effect
    modal.classList.remove('hidden');
    modalContent.classList.remove('modal-exit'); // Reset exit animation
    modalContent.classList.add('modal-enter'); // Apply enter animation
  
    document.body.classList.add('no-scroll');
  
    // Close modal when clicking the close button.
    document.getElementById('modal-close').onclick = function () {
      closeModal();
    };
  
    // Close modal when clicking outside the content.
    modal.onclick = function (event) {
      if (event.target === modal) {
        closeModal();
      }
    };
  
    // Close modal when pressing "Escape" key.
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeModal();
      }
    });
  }
  
  function closeModal() {
    const modal = document.getElementById('custom-modal');
    const modalContent = modal.querySelector('.modal-content');
  
    // Apply exit animation
    modalContent.classList.remove('modal-enter');
    modalContent.classList.add('modal-exit');
  
    // Wait for animation to finish before hiding modal
    setTimeout(() => {
      modal.classList.add('hidden');
      document.body.classList.remove('no-scroll');
    }, 300); // Match the exit animation duration
  }
  
  

  