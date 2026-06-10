const btnMonth = document.getElementById("month");
const btnYear = document.getElementById("year");
const btns = document.getElementById("btns");
const firstPlan = document.getElementById("first-plan");
const secondPlan = document.getElementById("second-plan");
const thirdPlan = document.getElementById("third-plan");
// Plan title/subtitle elements (added ids in template)
const title1 = document.getElementById("title1");
const subtitle1 = document.getElementById("subtitle1");
const title2 = document.getElementById("title2");
const subtitle2 = document.getElementById("subtitle2");
const title3 = document.getElementById("title3");
const subtitle3 = document.getElementById("subtitle3");

// Currency state
let isEGP = false;
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('phoneModal');
    
    // Only run if modal exists (user doesn't have phone number)
    if (modal) {
      const form = document.getElementById('phoneForm');
      const errorDiv = document.getElementById('phoneError');
      const submitBtn = form.querySelector('button[type="submit"]');
      const phoneInput = document.getElementById('phoneInput');
      const countryCodeSelect = document.getElementById('countryCode');
      const termsCheckbox = document.getElementById('termsCheckbox');
 
      // Focus on input after animation
      setTimeout(() => {
        phoneInput.focus();
      }, 500);
      
      // Form submission
      form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const countryCode = countryCodeSelect.value;
        const phoneNumber = phoneInput.value;
        const fullPhoneNumber = countryCode + phoneNumber;
        
        // Basic validation

        
        if (!phoneNumber) {
          showError('Please enter a phone number');
          return;
        }
        if (!termsCheckbox.checked) {
          showError('You must agree to the Terms and Conditions.');
          return;
       }
        // Validate phone format (basic number format)
        const phoneRegex = /^[0-9]{4,14}$/;
        if (!phoneRegex.test(phoneNumber)) {
          showError('Please enter a valid phone number (numbers only, 4-14 digits)');
          return;
        }
        
        // Disable submit button
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Saving...</span><i class="fas fa-spinner fa-spin"></i>';
        
        try {
          const response = await fetch('/add-phone-number/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({ 
              phone_number: fullPhoneNumber,
              country_code: countryCode,
              local_number: phoneNumber,
              terms_accepted: true   // ✅ send this to backend
            })
          });
          
          const data = await response.json();
          
          if (data.success) {
            // Success animation
            modal.style.animation = 'modalSlideOut 0.5s ease forwards';
            
            setTimeout(() => {
              modal.style.display = 'none';
              document.body.style.overflow = '';
              location.reload();
            }, 500);
          } else {
            showError(data.error || 'Failed to save phone number');
          }
        } catch (error) {
          showError('Network error. Please try again.');
        } finally {
          // Re-enable submit button
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<span>Save Phone Number</span><i class="fas fa-check"></i>';
        }
      });
      
      // Rest of your existing JavaScript code...
      function showError(message) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        
        // Hide error after 5 seconds
        setTimeout(() => {
          errorDiv.style.display = 'none';
        }, 5000);
      }
      
      // Prevent closing the modal by clicking outside
      modal.addEventListener('click', function(e) {
        if (e.target === modal) {
          // Gentle shake animation to indicate it can't be closed
          modal.style.animation = 'shake 0.5s ease-in-out';
          setTimeout(() => {
            modal.style.animation = '';
          }, 500);
        }
      });
      
      // Prevent closing with escape key
      document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
          e.preventDefault();
          e.stopPropagation();
          
          // Gentle shake animation
          modal.style.animation = 'shake 0.5s ease-in-out';
          setTimeout(() => {
            modal.style.animation = '';
          }, 500);
        }
      });
      
      // Add slide out animation
      const style = document.createElement('style');
      style.textContent = `
        @keyframes modalSlideOut {
          from {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
          to {
            opacity: 0;
            transform: translateY(-20px) scale(0.95);
          }
        }
      `;
      document.head.appendChild(style);
    }
  });





  
// Function to handle clicks outside the sidebar
function outsideClickListener(event) {
    const sidebar = document.getElementById('sidebar');
    const menuBtn = document.querySelector('.menu-btn');
    
    // Check if elements exist before using them
    if (!sidebar || !menuBtn) return;
    
    // Check if click is outside sidebar and not on the menu button
    if (!sidebar.contains(event.target) && !menuBtn.contains(event.target)) {
        sidebar.classList.remove('active');
        document.removeEventListener('click', outsideClickListener);
    }
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    
    sidebar.classList.toggle('active');

    // Add or remove the event listener based on sidebar state
    if (sidebar.classList.contains('active')) {
        document.addEventListener('click', outsideClickListener);
    } else {
        document.removeEventListener('click', outsideClickListener);
    }
}

function goTo(elementId) {
    const targetElement = document.getElementById(elementId);
    if (targetElement) {
        targetElement.scrollIntoView({ behavior: "smooth" });
        document.activeElement.blur(); // Optional: Blur the currently focused element
    }
}

// Global variable to store plans
let SUBSCRIPTION_PLANS = {
    monthly_plans: [],
    yearly_plans: []
};

// Fetch plans from the backend
async function fetchPlans() {
    try {
        const response = await fetch('/api/plans');
        if (!response.ok) {
            throw new Error('Failed to fetch plans');
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching plans:', error);
        return { monthly_plans: [], yearly_plans: [] };
    }
}

// Function to render features and add a subscribe button for a given plan
function renderPlanFeaturesAndButton(plan, container) {
    if (!container) return; // Check if container exists
    
    container.innerHTML = ""; // Clear existing content

    // Render features (skip items with 0 trials)
    plan.tools.forEach(tool => {
      if (!tool) return;
      const raw = Number(tool.max_trials) || 0;
      // Skip items with zero allowance
      if (raw <= 0) return;

      const featureDiv = document.createElement("div");
      featureDiv.classList.add("sides");

      const icon = document.createElement("i");
      icon.classList.add("fa-solid", "fa-circle-check");

      const featureText = document.createElement("span");

      // Determine display value and unit
      let displayValue = raw;
      let displayUnit = tool.unit || '';

      // Convert minutes to hours only when it's 60 minutes or more
      const section = document.getElementById("container-sub");
      const transHours = section && section.dataset.transHours ? section.dataset.transHours : "hours";
      if (displayUnit.toLowerCase() === "minutes" && raw >= 60) {
        displayValue = Math.floor(raw / 60);
        displayUnit = transHours;
      }

      featureText.textContent = `${tool.tool_name} ${displayValue.toLocaleString()} ${displayUnit}`;

      featureDiv.appendChild(icon);
      featureDiv.appendChild(featureText);

      container.appendChild(featureDiv);
    });

    // Add subscribe button
    const buttonContainer = document.createElement("div");
    buttonContainer.classList.add("div-container");
     
    const subscribeButton = document.createElement("button");
    subscribeButton.classList.add("offer-btn");
    subscribeButton.classList.add("plan-button");
    
    subscribeButton.type = "button";

    const buttonText = document.createElement("span");
    const section = document.getElementById("container-sub");
    buttonText.textContent = (section && section.dataset.transSubscribe) ? section.dataset.transSubscribe : "Subscribe";
    subscribeButton.appendChild(buttonText);

    subscribeButton.onclick = () => redirectToSubscribe(plan.name);

    buttonContainer.appendChild(subscribeButton);
    container.appendChild(buttonContainer);
}

// Function to handle the redirection
function redirectToSubscribe(planName) {
    const currency = isEGP ? "EGP" : "Dollar"; // Use the current currency state
    const url = `/subscribe?plan_name=${encodeURIComponent(planName)}&currency=${currency}`;
    window.location.href = url;
}

// Function to update prices based on currency
function updatePrices() {
    const price1 = document.getElementById("price1");
    const price2 = document.getElementById("price2");
    const price3 = document.getElementById("price3");

    // Check if price elements exist
    if (!price1 || !price2 || !price3) return;

    const plans = btnMonth && btnMonth.classList.contains("active") ? SUBSCRIPTION_PLANS.monthly_plans : SUBSCRIPTION_PLANS.yearly_plans;

    // Check if plans exist
    if (plans.length < 3) return;

    if (isEGP) {
        price1.textContent = `EGP ${plans[0].price_egp}`;
        price2.textContent = `EGP ${plans[1].price_egp}`;
        price3.textContent = `EGP ${plans[2].price_egp}`;
    } else {
        price1.textContent = `$${plans[0].price_usd}`;
        price2.textContent = `$${plans[1].price_usd}`;
        price3.textContent = `$${plans[2].price_usd}`;
    }
}

// Function to update durations based on the selected plan type (uses translated strings from template)
function updateDurations() {
    const duration1 = document.getElementById("duration1");
    const duration2 = document.getElementById("duration2");
    const duration3 = document.getElementById("duration3");
    const section = document.getElementById("container-sub");
    const transMonthly = section && section.dataset.transMonthly ? section.dataset.transMonthly : "Monthly";
    const transYearly = section && section.dataset.transYearly ? section.dataset.transYearly : "Yearly";

    if (!duration1 || !duration2 || !duration3) return;

    if (btnMonth && btnMonth.classList.contains("active")) {
        duration1.textContent = transMonthly;
        duration2.textContent = transMonthly;
        duration3.textContent = transMonthly;
    } else {
        duration1.textContent = transYearly;
        duration2.textContent = transYearly;
        duration3.textContent = transYearly;
    }
}

// Handle button clicks to switch between monthly and yearly plans
function handleButtonClick(event) {
    const value = event.target.dataset.value;

    if (value === "month") {
        if (btns) btns.style.left = "10px"; // Position for monthly
        if (btnMonth) btnMonth.classList.add("active");
        if (btnYear) btnYear.classList.remove("active");

        // Render monthly plans
        if (SUBSCRIPTION_PLANS.monthly_plans.length >= 3) {
          renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[0], firstPlan);
          renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[1], secondPlan);
          renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[2], thirdPlan);
          // update titles to reflect the selected plans (use translated display_name)
          if (title1) title1.textContent = SUBSCRIPTION_PLANS.monthly_plans[0].display_name || SUBSCRIPTION_PLANS.monthly_plans[0].name || title1.textContent;
          if (title2) title2.textContent = SUBSCRIPTION_PLANS.monthly_plans[1].display_name || SUBSCRIPTION_PLANS.monthly_plans[1].name || title2.textContent;
          if (title3) title3.textContent = SUBSCRIPTION_PLANS.monthly_plans[2].display_name || SUBSCRIPTION_PLANS.monthly_plans[2].name || title3.textContent;
        }
    } else if (value === "year") {
        if (btns) btns.style.left = "100px"; // Position for yearly
        if (btnYear) btnYear.classList.add("active");
        if (btnMonth) btnMonth.classList.remove("active");

        // Render yearly plans
        if (SUBSCRIPTION_PLANS.yearly_plans.length >= 3) {
          renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.yearly_plans[0], firstPlan);
          renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.yearly_plans[1], secondPlan);
          renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.yearly_plans[2], thirdPlan);
          // update titles to reflect the selected plans (use translated display_name)
          if (title1) title1.textContent = SUBSCRIPTION_PLANS.yearly_plans[0].display_name || SUBSCRIPTION_PLANS.yearly_plans[0].name || title1.textContent;
          if (title2) title2.textContent = SUBSCRIPTION_PLANS.yearly_plans[1].display_name || SUBSCRIPTION_PLANS.yearly_plans[1].name || title2.textContent;
          if (title3) title3.textContent = SUBSCRIPTION_PLANS.yearly_plans[2].display_name || SUBSCRIPTION_PLANS.yearly_plans[2].name || title3.textContent;
        }
    }

    updatePrices(); // Update prices after switching plans
    updateDurations(); // Update durations after switching plans
}

// Currency toggle button (uses translated strings from template)
const currencyBtn = document.getElementById("currency-btn");
if (currencyBtn) {
    const section = document.getElementById("container-sub");
    const transEgp = section && section.dataset.transSwitchEgp ? section.dataset.transSwitchEgp : "Switch to EGP";
    const transUsd = section && section.dataset.transSwitchUsd ? section.dataset.transSwitchUsd : "Switch to USD";
    currencyBtn.addEventListener("click", function () {
        isEGP = !isEGP;
        updatePrices();
        currencyBtn.textContent = isEGP ? transUsd : transEgp;
    });
}

// Initialize the page
async function initialize() {
    // Only initialize pricing elements if they exist on the page
    if (btnMonth && btnYear && firstPlan && secondPlan && thirdPlan) {
        const data = await fetchPlans();
        SUBSCRIPTION_PLANS.monthly_plans = data.monthly_plans;
        SUBSCRIPTION_PLANS.yearly_plans = data.yearly_plans;

        // Render monthly plans by default
        if (SUBSCRIPTION_PLANS.monthly_plans.length >= 3) {
            renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[0], firstPlan);
            renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[1], secondPlan);
            renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[2], thirdPlan);
          // set initial titles (use translated display_name from API)
          if (title1) title1.textContent = SUBSCRIPTION_PLANS.monthly_plans[0].display_name || SUBSCRIPTION_PLANS.monthly_plans[0].name || title1.textContent;
          if (title2) title2.textContent = SUBSCRIPTION_PLANS.monthly_plans[1].display_name || SUBSCRIPTION_PLANS.monthly_plans[1].name || title2.textContent;
          if (title3) title3.textContent = SUBSCRIPTION_PLANS.monthly_plans[2].display_name || SUBSCRIPTION_PLANS.monthly_plans[2].name || title3.textContent;
        }

        // Set initial state
        btnMonth.classList.add("active");
        updatePrices();
        updateDurations();

        // Add event listeners for the buttons
        btnMonth.addEventListener("click", handleButtonClick);
        btnYear.addEventListener("click", handleButtonClick);
    }
}

// Start the app
initialize();

// Only add dropdown functionality if the elements exist
const productMenu = document.getElementById("product-menu"); // Make sure this exists
const dropdownMenu = document.getElementById("dropdown-menu");

if (productMenu) {
    productMenu.addEventListener("click", function (e) {
        // Only prevent default if clicking on the menu itself, not the links
        if (!e.target.closest('.dropdown-item')) {
            e.preventDefault();
            e.stopPropagation();
            
            const dropdownMenu = document.getElementById("dropdown-menu");
            const dropdownIcon = document.getElementById("dropdown-icon");

            if (dropdownMenu && dropdownIcon) {
                dropdownMenu.classList.toggle("visible");
                dropdownIcon.classList.toggle("rotate");
            }
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        const dropdownMenu = document.getElementById("dropdown-menu");
        const dropdownIcon = document.getElementById("dropdown-icon");
        
        if (dropdownMenu && dropdownMenu.classList.contains("visible") && 
            !productMenu.contains(e.target) &&
            !dropdownMenu.contains(e.target)) {
            dropdownMenu.classList.remove("visible");
            if (dropdownIcon) dropdownIcon.classList.remove("rotate");
        }
    });
    
    // Allow links to work normally
    if (dropdownMenu) {
        dropdownMenu.addEventListener('click', function(e) {
            if (e.target.closest('.dropdown-item')) {
                // Allow the link to work normally
                dropdownMenu.classList.remove("visible");
                const dropdownIcon = document.getElementById("dropdown-icon");
                if (dropdownIcon) dropdownIcon.classList.remove("rotate");
            }
        });
    }
}


const sidebarLinks = document.querySelectorAll('.sidebar-nav .nav-link');
sidebarLinks.forEach(link => {
    link.addEventListener('click', () => {
        const sidebar = document.getElementById('sidebar');
        if (sidebar && sidebar.classList.contains('active')) {
            sidebar.classList.remove('active');
            document.removeEventListener('click', outsideClickListener);
        }
    });
});