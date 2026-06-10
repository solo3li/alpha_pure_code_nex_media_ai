 
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrfToken = getCookie("csrftoken");
 

document.addEventListener("DOMContentLoaded", function () {
    document.addEventListener('click', handleClickOutside);
    const chatBox = document.getElementById("chat-box");
    const fileInputContainer = document.getElementById('file-input-container');
    const messageInput = document.getElementById("message-input");
    const modelSelect = document.getElementById("model-select");
    const initialModel = document.getElementById('model-select').value;
    const sendBtn = document.getElementById("send-btn");
    const fileInput = document.getElementById("file-input");
    const fileIcon = document.getElementById("file-icon"); // Icon to change color
    const maxSize = 2 * 1024 * 1024; // 2MB in bytes
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (initialModel !== "gpt-4o") {
        fileInputContainer.style.display = "none";
    }
    modelSelect.addEventListener("change", function (event) {
        const previousValue = this.dataset.previousValue || "gpt-3.5-turbo"; // Store previous value
        const selectedValue = this.value;
    
        if (previousValue !== selectedValue) {
            const confirmChange = confirm("Are you sure you want to change the model?");
            if (!confirmChange) {
                this.value = previousValue; // Revert selection if user cancels
                return;
            }
        }
    
        this.dataset.previousValue = selectedValue; // Update previous value
    
        // Show file input if "GPT-4o" is selected, otherwise hide it
        fileIcon.style.display = selectedValue === "gpt-4o" ? "block" : "none";
        if (fileInput) {
            fileInput.value = ''; // Clear selected files
            fileIcon.style.color = "white"; // Reset icon color to default
        }
        updateTrialCount(selectedValue);
    
        // 🔹 Clear all messages when model is changed
        document.getElementById("chat-box").innerHTML = "";
    });
    

    // Initialize the previous value
    modelSelect.dataset.previousValue = modelSelect.value;
    messageInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) { // Prevents new line when Shift is not pressed
            event.preventDefault(); // Prevents default newline behavior
            sendBtn.click(); // Triggers send button click
        }
    });
 
    fileInput.addEventListener("change", function () {
        const file = fileInput.files[0];
        
        if (file) {
            // Check file type
            if (!allowedTypes.includes(file.type)) {
                alert('Please select an image file (JPEG, PNG, GIF, or WEBP)');
                fileInput.value = ''; // Clear the input
                fileIcon.style.color = "white";
                return;
            }
            
            // Check file size
            if (file.size > maxSize) {
                alert('File size must be less than 2MB');
                fileInput.value = ''; // Clear the input
                fileIcon.style.color = "white";
                return;
            }
            
            fileIcon.style.color = "green"; // File is valid
        } else {
            fileIcon.style.color = "white";
        }
    });
    function formatMessage(text, isUserMessage = false) {
        // Handle code blocks first (your original logic)
        let formattedText = text.replace(/```([\w]*)\n([\s\S]*?)```/g, (match, lang, code) => {
            const cleanCode = code.trim()
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
    
            return `
                <div class="code-block">
                    <div class="code-header">
                        <span class="code-language">${lang || 'plaintext'}</span>
                        <button class="copy-btn" onclick="copyCode(this)" title="Copy code"
                            style="
                                height: fit-content;
                                width: fit-content;
                                margin-right: 10px;
                                display: flex;
                                align-items: center;
                                gap: 4px;
                                padding: 4px 8px;
                                border: 1px solid #d1d5da;
                                border-radius: 4px;
                                background-color: white;
                                cursor: pointer;
                                font-size: 0.9em;
                                transition: background-color 0.2s;
                            ">
                            <span class="copy-icon">📋</span>
                        </button>
                    </div>
                    <div class="code-container">
                        <pre><code class="language-${lang || 'plaintext'}">${cleanCode}</code></pre>
                    </div>
                </div>
            `;
        });
        formattedText = formattedText.replace(/<a href='([^']+)' target='_blank'>([^<]+)<\/a>/g, (match, href, text) => {
            return `<a href="${href}" target="_blank" class="message-link" style="color: #007bff; text-decoration: underline;">${text}</a>`;
        });
    
        // Handle inline code (your original logic)
        formattedText = formattedText.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    
        // Handle headers (h1, h2, h3)
        formattedText = formattedText.replace(/^### (.*$)/gm, '<h3>$1</h3>');
        formattedText = formattedText.replace(/^## (.*$)/gm, '<h2>$1</h2>');
        formattedText = formattedText.replace(/^# (.*$)/gm, '<h1>$1</h1>');
    
        // Handle bold (**text**)
        formattedText = formattedText.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
    
        // Handle italic (*text*)
        formattedText = formattedText.replace(/\*(.*?)\*/g, '<i>$1</i>');
    
        // Handle bold-italic (***text***)
        formattedText = formattedText.replace(/\*\*\*(.*?)\*\*\*/g, '<b><i>$1</i></b>');
    
        // Handle unordered lists (- item or * item)
        formattedText = formattedText.replace(/(?:^|\n)([-*]) (.*)/g, (match, bullet, item) => {
            return `<ul><li>${item}</li></ul>`;
        });

        
    
        // Apply line-height for better spacing only for non-user messages
        if (!isUserMessage) {
            formattedText = `<div style="line-height: 1.6;">${formattedText}</div>`;
        }
    
        return formattedText;
    }
    

    
    
    function appendMessage(role, text, imageSrc = null) {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", role);
        fileIcon.style.color = "white";
    
        if (imageSrc) {
            const img = document.createElement("img");
            img.src = imageSrc;
            img.classList.add("chat-image");
            img.classList.add("message", "user-image");
            chatBox.appendChild(img);
        }
    
        if (text) {
            const textDiv = document.createElement("div");
            textDiv.classList.add("message-content");
    
            try {
                textDiv.innerHTML = formatMessage(text);
            } catch (error) {
                console.error("Error formatting message:", error);
                textDiv.textContent = text;
            }
    
            messageDiv.appendChild(textDiv);
        }
    
        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatCodeBlocks(text) {
        let formattedText = text;
        
        // Handle complete code blocks
        formattedText = formattedText.replace(/```([\w]*)\n([\s\S]*?)```/g, (match, lang, code) => {
            const cleanCode = code.trim()
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');

                return `
                <div class="code-block">
                    <div class="code-header">
                        <span class="code-language">${lang || 'plaintext'}</span>
                        <button class="copy-btn" onclick="copyCode(this)" title="Copy code"
                            style="
                                height: fit-content;
                                width: fit-content;
                                margin-right: 10px;
                                display: flex;
                                align-items: center;
                                gap: 4px;
                                padding: 4px 8px;
                                border: 1px solid #d1d5da;
                                border-radius: 4px;
                                background-color: white;
                                cursor: pointer;
                                font-size: 0.9em;
                                transition: background-color 0.2s;
                            ">
                            <span class="copy-icon">📋</span>
                        </button>
                    </div>
                    <div class="code-container">
                        <pre><code class="language-${lang || 'plaintext'}">${cleanCode}</code></pre>
                    </div>
                </div>
            `;
        });

        // Handle incomplete code blocks (missing closing tags)
        formattedText = formattedText.replace(/```([\w]*)\n([\s\S]*?)$/g, (match, lang, code) => {
            if (!match.endsWith('```')) {
                const cleanCode = code.trim()
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');

                    return `
                    <div class="code-block">
                        <div class="code-header">
                            <span class="code-language">${lang || 'plaintext'}</span>
                            <button class="copy-btn" onclick="copyCode(this)" title="Copy code"
                                style="
                                    height: fit-content;
                                    width: fit-content;
                                    margin-right: 10px;
                                    display: flex;
                                    align-items: center;
                                    gap: 4px;
                                    padding: 4px 8px;
                                    border: 1px solid #d1d5da;
                                    border-radius: 4px;
                                    background-color: white;
                                    cursor: pointer;
                                    font-size: 0.9em;
                                    transition: background-color 0.2s;
                                ">
                                <span class="copy-icon">📋</span>
                            </button>
                        </div>
                        <div class="code-container">
                            <pre><code class="language-${lang || 'plaintext'}">${cleanCode}</code></pre>
                        </div>
                    </div>
                `;
            }
            return match;
        });

        // Handle inline code
        formattedText = formattedText.replace(/`([^`]+)`/g, (match, code) => {
            return `<code class="inline-code">${code}</code>`;
        });

        return formattedText;
    }

    window.copyCode = function(button) {
        const codeBlock = button.closest('.code-block').querySelector('code');
        const code = codeBlock.textContent;
    
        navigator.clipboard.writeText(code).then(() => {
            button.textContent = '✅ Copied';
            setTimeout(() => {
                button.textContent = '📋 Copy';
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
            alert('Failed to copy code to clipboard');
        });
    };
    

    async function sendMessage() {
        const message = messageInput.value.trim();
        const model = modelSelect.value;
        const file = fileInput.files[0];
        let imageData = null;
    
        if (!message) {
            alert("Please enter a message before sending.");
            return;
        }
    
        if (file && file.type.startsWith("image")) {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            await new Promise(resolve => {
                reader.onload = () => {
                    imageData = reader.result;
                    resolve();
                };
            });
        }
    
        // Append user message
        appendMessage("user", message, imageData);
        messageInput.value = "";
        fileInput.value = ""; // Clear file after sending
    
        // Add loading indicator for assistant response
        const loadingMessage = document.createElement("div");
        loadingMessage.classList.add("message", "assistant");
        loadingMessage.innerHTML = `
            <div class="loading-spinner"></div> 
        `;
        chatBox.appendChild(loadingMessage);
        chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll to bottom
       
        try {
            const response = await fetch("/GPT/chat/", {
                method: "POST",
                headers: { "Content-Type": "application/json" ,'X-CSRFToken': csrfToken   },
                body: JSON.stringify({ message, model, image: imageData }),
            });
    
            const data = await response.json();
    
            // Remove loading animation and replace with actual response
            chatBox.removeChild(loadingMessage);
            appendMessage("assistant", data.response);
        } catch (error) {
            console.error("Error:", error);
            chatBox.removeChild(loadingMessage);
            appendMessage("assistant", "⚠️ Error fetching response. Please try again.");
        }
    
        updateTrialCount(model);
    }
    

    sendBtn.addEventListener("click", sendMessage);
    
    modelSelect.addEventListener("change", function (event) {
        const previousValue = this.dataset.previousValue || "gpt-3.5-turbo";
        const selectedValue = this.value;
    
        if (previousValue !== selectedValue) {
            const confirmChange = confirm("Are you sure you want to change the model?");
            if (!confirmChange) {
                this.value = previousValue;
                return;
            }
        }
    
        this.dataset.previousValue = selectedValue;
    
        // Show/hide file input container based on model selection
        const fileInputContainer = document.getElementById('file-input-container');
        if (selectedValue === "gpt-4o") {
            fileInputContainer.style.display = "flex"; // or "block" depending on your layout
        } else {
            fileInputContainer.style.display = "none";
            if (fileInput) {
                fileInput.value = ''; // Clear selected files
                fileIcon.style.color = "white"; // Reset icon color to default
            }
        }
        
        updateTrialCount(selectedValue);
    
        // Clear all messages when model is changed
        document.getElementById("chat-box").innerHTML = "";
    });

    
    // Initialize the previous value
    modelSelect.dataset.previousValue = modelSelect.value;
    

    async function sendImageToServer() {
        const fileInput = document.getElementById('imageInput');
        const file = fileInput.files[0];
        const reader = new FileReader();
    
        reader.onloadend = function() {
            const base64data = reader.result.split(',')[1]; // Remove the prefix
            const data = {
                message: "What's in this image?",
                model: "gpt-4o",
                image: base64data
            };
    
            fetch('/GPT/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                    
                },
                body: JSON.stringify(data),
            })
            .then(response => response.json())
            .then(data => {
                console.log('Success:', data);
            })
            .catch((error) => {
                console.error('Error:', error);
            });
        };
    
        if (file) {
            reader.readAsDataURL(file);
        }
    }

    function updateTrialCount(modelName) {
        $.ajax({
            url: '/GPT/get_trials_left',
            type: 'GET',
            data: { tool_name: modelName },
            success: function(data) {
                if (data.trials_left !== undefined) {
                    // Update the correct element with class .trial-count
                    document.querySelector('.trial-count').textContent = data.trials_left;
                    
                    if(data.trials_left === 0) {
                        // Make sure you have an element with ID trialPopup
                        $('#trialPopup').fadeIn();
                    }
                } else {
                    console.error('Error: Invalid response for trials left');
                }
            },
            error: function(xhr, status, error) {
                console.error('Failed to fetch the updated trial count:', error);
            }
        });
    }

    updateTrialCount(modelSelect.value);
});
