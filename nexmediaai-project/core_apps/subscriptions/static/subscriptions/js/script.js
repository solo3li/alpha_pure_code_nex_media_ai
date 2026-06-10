


document.addEventListener("DOMContentLoaded", function () {
 
    const paymobButton = document.getElementById('paymob-button'); // Paymob
    const loadingScreen = document.getElementById('loading-screen');
    const errorPopup = document.getElementById('error-popup');
    const errorMessageElement = document.getElementById('error-message');
    const errorDetailsElement = document.getElementById('error-details');
    const closeErrorButton = document.getElementById('error-popup-close');

    const validationMessages = {
        name: "Please enter your name.",
        cardnumber: "Please enter a valid card number.",
        expirationdate: "Expiration date format must be MM/YY.",
        securitycode: "CVV must be 3 digits."
    };

    // Function to update the URL with the selected currency
    function updateCurrencyInURL(currency) {
        const currentURL = new URL(window.location.href);
        currentURL.searchParams.set('currency', currency);
        window.history.replaceState({}, '', currentURL.toString());
    }

    // Function to update the currency and amount in the DOM
    function updateCurrencyAndAmount(currency, amount) {
        const priceElement = document.querySelector('.price');
        const subtotalElement = document.querySelector('.billing-row:nth-child(1) span:last-child');
        const totalElement = document.querySelector('.billing-row.total span:last-child');

        if (priceElement) priceElement.textContent = `${currency} ${amount}`;
        if (subtotalElement) subtotalElement.textContent = `${currency} ${amount}`;
        if (totalElement) totalElement.textContent = `${currency} ${amount}`;
    }

function paymobPayment() {
    // Hide payment buttons
 
    const paymobButton = document.getElementById('paymob-button');
    
 
    if (paymobButton) paymobButton.style.display = 'none';

    // Get the .big element
    const bigDiv = document.querySelector('.big');
    if (bigDiv) {
        // Hide all child elements inside .big
        Array.from(bigDiv.children).forEach(child => {
            child.style.display = 'none';
        });

        // Expand .big to 100% width
        bigDiv.style.width = '100%';
    }

    // Show loading screen
    const loadingScreen = document.getElementById('loading-screen');
    loadingScreen.style.display = 'flex';

    // Get CSRF token
    function getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]').content || 
               document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    // Fetch payment info from the backend
    fetch(`/get-payment-form/?plan_name=${encodeURIComponent(planName)}&provider=paymob`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()  // Include CSRF token for GET if needed
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Failed to fetch payment info. Status: ${response.status}`);
        }
        return response.json();
    })
    .then(paymentInfo => {
        // Prepare the data for the /pay endpoint
        const formData = {
            plan_name: planName,
            provider_name: 'paymob',
            payment_info: paymentInfo
        };

        // Send the data to /pay to generate the payment key
        return fetch('/pay/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()  // CRITICAL: Include CSRF token
            },
            body: JSON.stringify(formData)
        });
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error || `Payment request failed with status: ${response.status}`); });
        }
        return response.json();
    })
    .then(data => {
        // Hide loading screen
        loadingScreen.style.display = 'none';

        // Check if the payment key was generated successfully
        if (!data.iframe_url) {
            throw new Error(data.error || "Failed to generate payment iframe URL.");
        }

        // Replace the content of the 'big' div with the Paymob iframe
        if (bigDiv) {
            bigDiv.innerHTML = `
                <iframe 
                    id="paymob-iframe" 
                    src="${data.iframe_url}" 
                    style="width: 100%; height: 100%; border: none;"
                    allow="payment *"
                ></iframe>
            `;
            bigDiv.style.height = '100vh';
        }
    })
    .catch(error => {
        console.error('Payment error:', error);
        // Hide loading screen in case of error
        loadingScreen.style.display = 'none';

        // Show error popup
        showErrorPopup('Payment Error', error.message || 'An unexpected error occurred. Please try again.');

        // Show payment buttons again in case of error
 
        if (paymobButton) paymobButton.style.display = 'block';

        // Reset .big and show child elements again in case of error
        if (bigDiv) {
            bigDiv.style.width = '';
            bigDiv.style.height = '';
            Array.from(bigDiv.children).forEach(child => {
                child.style.display = '';
            });
        }
    });
}

    function closeErrorPopup() {
        errorPopup.style.display = 'none';
    }

  
    if (closeErrorButton) {
        closeErrorButton.addEventListener('click', closeErrorPopup);
    }

    // Check URL for currency=EGP and trigger Paymob payment
    const urlParams = new URLSearchParams(window.location.search);
    const currency = urlParams.get('currency');

    if (currency === 'EGP') {
        paymobPayment();
    }

    // Paymob Button Click Event
    paymobButton.addEventListener('click', function (event) {
        event.preventDefault();

        // Redirect to the same page with currency=EGP
        const currentURL = new URL(window.location.href);
        currentURL.searchParams.set('currency', 'EGP');
        window.location.href = currentURL.toString();
    });


});
 

// Handle the "Confirm Payment" button click
 