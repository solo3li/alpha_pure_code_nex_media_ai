const btnMonth = document.getElementById("month");
const btnYear = document.getElementById("year");
const btns = document.getElementById("btns");
const firstPlan = document.getElementById("first-plan");
const secondPlan = document.getElementById("second-plan");

// Currency state
let isEGP = false;

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
    container.innerHTML = ""; // Clear existing content

    // Render features
    plan.tools.forEach(tool => {
        const featureDiv = document.createElement("div");
        featureDiv.classList.add("sides");

        const icon = document.createElement("i");
        icon.classList.add("fa-solid", "fa-circle-check");

        const featureText = document.createElement("span");
        featureText.textContent = `${tool.tool_name} ${tool.max_trials.toLocaleString()} ${tool.unit}`;

        featureDiv.appendChild(icon);
        featureDiv.appendChild(featureText);

        container.appendChild(featureDiv);
    });

    // Add subscribe button
    const buttonContainer = document.createElement("div");
    buttonContainer.classList.add("div-container");

    const subscribeButton = document.createElement("button");
    subscribeButton.classList.add("offer-btn");
    subscribeButton.type = "button";

    const buttonText = document.createElement("span");
    buttonText.textContent = "Subscribe";
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

    const plans = btnMonth.classList.contains("active") ? SUBSCRIPTION_PLANS.monthly_plans : SUBSCRIPTION_PLANS.yearly_plans;

    if (isEGP) {
        price1.textContent = `EGP ${plans[0].price_egp}`;
        price2.textContent = `EGP ${plans[1].price_egp}`;
    } else {
        price1.textContent = `$${plans[0].price_usd}`;
        price2.textContent = `$${plans[1].price_usd}`;
    }
}

// Function to update durations based on the selected plan type
function updateDurations() {
    const duration1 = document.getElementById("duration1");
    const duration2 = document.getElementById("duration2");

    if (btnMonth.classList.contains("active")) {
        duration1.textContent = "Monthly";
        duration2.textContent = "Monthly";
    } else {
        duration1.textContent = "Yearly";
        duration2.textContent = "Yearly";
    }
}

// Handle button clicks to switch between monthly and yearly plans
function handleButtonClick(event) {
    const value = event.target.dataset.value;

    if (value === "month") {
        btns.style.left = "10px"; // Position for monthly
        btnMonth.classList.add("active");
        btnYear.classList.remove("active");

        // Render monthly plans
        renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[0], firstPlan);
        renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[1], secondPlan);
    } else if (value === "year") {
        btns.style.left = "100px"; // Position for yearly
        btnYear.classList.add("active");
        btnMonth.classList.remove("active");

        // Render yearly plans
        renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.yearly_plans[0], firstPlan);
        renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.yearly_plans[1], secondPlan);
    }

    updatePrices(); // Update prices after switching plans
    updateDurations(); // Update durations after switching plans
}

// Currency toggle button
const currencyBtn = document.getElementById("currency-btn");
currencyBtn.addEventListener("click", function () {
    isEGP = !isEGP; // Toggle between USD and EGP
    updatePrices(); // Update the displayed prices
    currencyBtn.textContent = isEGP ? "Switch to USD" : "Switch to EGP";
});

// Initialize the page
async function initialize() {
    const data = await fetchPlans();
    SUBSCRIPTION_PLANS.monthly_plans = data.monthly_plans;
    SUBSCRIPTION_PLANS.yearly_plans = data.yearly_plans;

    // Render monthly plans by default
    renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[0], firstPlan);
    renderPlanFeaturesAndButton(SUBSCRIPTION_PLANS.monthly_plans[1], secondPlan);

    // Set initial state
    btnMonth.classList.add("active");
    updatePrices();
    updateDurations();

    // Add event listeners for the buttons
    btnMonth.addEventListener("click", handleButtonClick);
    btnYear.addEventListener("click", handleButtonClick);
}

// Start the app
initialize();


document.getElementById("product-menu").addEventListener("click", function () {
  const dropdownMenu = document.getElementById("dropdown-menu");
  const dropdownIcon = document.getElementById("dropdown-icon");

  dropdownMenu.classList.toggle("visible");
  dropdownIcon.classList.toggle("rotate");
});