export function initializeCart() {
    document.querySelectorAll('.add-to-cart-form').forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const variantId = form.dataset.variantId;
            if (!variantId) {
                showNotification('Please select a variant', true);
                return;
            }
            
            const url = `/cart/add/${variantId}/`;
            const notification = createNotificationElement();
            
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCSRFToken(form),
                        'Content-Type': 'application/json',
                    },
                });
                
                const data = await response.json();
                handleResponse(data, response.ok, notification);
            } catch (error) {
                handleError(error, notification);
            }
        });
    });
}

function getCSRFToken(form) {
    return form.querySelector('input[name="csrfmiddlewaretoken"]').value;
}

function createNotificationElement() {
    const notification = document.createElement('div');
    notification.className = 'cart-notification';
    document.body.appendChild(notification);
    return notification;
}

function showNotification(message, isError = false) {
    const notification = createNotificationElement();
    notification.classList.add('show', isError ? 'error' : 'success');
    notification.innerHTML = `
        <i class="fas ${isError ? 'fa-exclamation-circle' : 'fa-check-circle'}"></i>
        ${message}
    `;
    setTimeout(() => notification.remove(), 3000);
}

function handleResponse(data, isSuccess, notification) {
    if (isSuccess && data.success) {
        showNotification(data.message);
        updateCartCounter(data.cart_total_quantity); // Match the view's response
    } else {
        throw new Error(data.error || 'Error adding item to cart');
    }
}

function handleError(error, notification) {
    console.error('Cart Error:', error);
    showNotification(error.message || 'Error adding item to cart', true);
}

function updateCartCounter(count) {
    const counter = document.querySelector('#cart-counter'); // Adjust selector as needed
    if (counter) counter.textContent = count;
}

document.addEventListener('DOMContentLoaded', initializeCart);