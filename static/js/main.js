/**
 * Main JavaScript file for Kairos LMS
 */

// Utility functions
const KairosLMS = {
    // Format date to readable format
    formatDate: function(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    },
    
    // Show notification toast
    showNotification: function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        
        const toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            const container = document.createElement('div');
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(container);
            container.appendChild(toast);
        } else {
            toastContainer.appendChild(toast);
        }
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // Remove the toast after it's hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    },
    
    // API error handler
    handleApiError: function(error, message = 'An error occurred') {
        console.error(error);
        this.showNotification(`${message}: ${error.message}`, 'danger');
    },
    
    // Format priority
    getPriorityClass: function(priority) {
        return priority >= 7 ? 'priority-high' : 
               priority >= 4 ? 'priority-medium' : 'priority-low';
    },
    
    // Format priority label
    getPriorityLabel: function(priority) {
        return priority >= 7 ? 'High' : 
               priority >= 4 ? 'Medium' : 'Low';
    }
};

// Add event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add toast container to body
    if (!document.querySelector('.toast-container')) {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(container);
    }
    
    // Log that the app is ready
    console.log('Kairos LMS initialized');
});