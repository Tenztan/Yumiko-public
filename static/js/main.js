// Activity tracking variables
let hasShownIdleMessage = false;
let isUserActive = true;
let lastActivityTime = Date.now();
const IDLE_TIMEOUT = 70000; // 5 minutes in milliseconds
let lastVisibilityState = !document.hidden;
let isMobile = false;

// Proactive chat variables
let lastProactiveMessage = Date.now();
const PROACTIVE_INTERVAL = 60000; // 2 minutes in millisecond
const PROACTIVE_CHANCE = 0.7; // 30% chance to initiate conversation

// Detect if user is on mobile device
function checkMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// Update the activity status
function updateUserActivity() {
    lastActivityTime = Date.now();
    lastProactiveMessage = Date.now(); // Reset proactive timer when user is active

    if (!isUserActive) {
        isUserActive = true;
        hasShownIdleMessage = false;
    }
}

// Check if user has gone idle
function checkIdleStatus() {
    if (isUserActive && !hasShownIdleMessage && (Date.now() - lastActivityTime > IDLE_TIMEOUT)) {
        isUserActive = false;
        hasShownIdleMessage = true;

        fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: "[SYSTEM] User inactive",
                trigger: "idle"
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.response) {
                appendMessage("Yumiko", data.response);
                document.title = "Yumiko misses you...";
            }
        });
    }
}

// Proactive chat functions
function checkProactiveChat() {
    // Don't send proactive messages if user is inactive or page is hidden
    if (!isUserActive || document.hidden) {
        return;
    }

    // Check if enough time has passed since last proactive message
    if (Date.now() - lastProactiveMessage > PROACTIVE_INTERVAL) {
        // Random chance to initiate conversation
        if (Math.random() < PROACTIVE_CHANCE) {
            sendProactiveMessage();
        }
        lastProactiveMessage = Date.now();
    }
}

function sendProactiveMessage() {
    fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            message: "[SYSTEM] Proactive message",
            trigger: "proactive"
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.response) {
            showTypingIndicator();
            // Add slight delay to simulate typing
            setTimeout(() => {
                hideTypingIndicator();
                appendMessage("Yumiko", data.response);
            }, 1500);
        }
    })
    .catch(error => console.error('Error:', error));
}

// Initialize activity tracking and proactive chat
document.addEventListener('DOMContentLoaded', function() {
    // Detect mobile device
    isMobile = checkMobile();

    // Desktop events
    const desktopEvents = ['mousemove', 'keypress', 'scroll', 'click'];

    // Mobile-specific events
    const mobileEvents = [
        'touchstart',
        'touchmove',
        'touchend',
        'orientationchange',
        'resize'
    ];

    // Combine events based on device type
    const eventsToTrack = isMobile ?
        [...mobileEvents, 'scroll', 'click'] :
        desktopEvents;

    // Track user activity for all relevant events
    eventsToTrack.forEach(event => {
        document.addEventListener(event, updateUserActivity, { passive: true });
    });

    // Check idle status periodically
    setInterval(checkIdleStatus, 60000);

    // Start proactive chat checker
    setInterval(checkProactiveChat, 20000);

    // Handle page visibility changes
    document.addEventListener('visibilitychange', function() {
        const isVisible = !document.hidden;

        if (isVisible !== lastVisibilityState) {
            lastVisibilityState = isVisible;

            if (isVisible) {
                // Handle return to app/tab
                fetch("/chat", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        message: "[SYSTEM] User returned",
                        trigger: "return"
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.response) {
                        appendMessage("Yumiko", data.response);
                        document.title = "Yumiko";
                    }
                });
            } else {
                // Handle leaving app/tab
                lastActivityTime = Date.now() - IDLE_TIMEOUT;
                hasShownIdleMessage = false;
                isUserActive = true;
            }
        }
    });

    // Mobile-specific handlers
    if (isMobile) {
        // Handle app going to background on mobile
        document.addEventListener('pagehide', function() {
            lastActivityTime = Date.now() - IDLE_TIMEOUT;
            hasShownIdleMessage = false;
            isUserActive = true;
        });

        // Handle app returning from background on mobile
        document.addEventListener('pageshow', function() {
            if (document.visibilityState === 'visible') {
                fetch("/chat", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        message: "[SYSTEM] User returned",
                        trigger: "return"
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.response) {
                        appendMessage("Yumiko", data.response);
                        document.title = "Yumiko";
                    }
                });
            }
        });
    }

    // Check session status
    checkSessionStatus();
});

// Message handling functions
document.getElementById("send-button").onclick = sendMessage;
document.getElementById("user-input").addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
});

function checkSessionStatus() {
    fetch('/check_session')
        .then(response => response.json())
        .then(data => {
            if (data.logged_in && !data.is_guest) {
                // Hide create account button if it exists
                let createAccountBtn = document.querySelector('.log-back');
                if (createAccountBtn) {
                    createAccountBtn.style.display = 'none';
                }
            }
        });
}

let messageCount = 0;
let hasShownAccountPrompt = false;

function sendMessage() {
    let userInput = document.getElementById("user-input").value;
    if (userInput.trim() === "") return;

    // Display user's message
    appendMessage("USER", userInput);

    // Clear input
    document.getElementById("user-input").value = "";

    // Show typing indicator
    showTypingIndicator();

    // Send message to backend
    fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: userInput })
    })
    .then(response => response.json())
    .then(data => {
        // Hide typing indicator
        hideTypingIndicator();

        // Display bot's response
        appendMessage("Yumiko", data.response);

        // Increment message counter
        messageCount++;

        // Check if we should show account creation prompt
        if (messageCount >= 3 && !hasShownAccountPrompt) {
            hasShownAccountPrompt = true;
            appendCreateAccountMessage();
        }

        // Scroll to bottom
        let chatBox = document.getElementById("chat-box");
        chatBox.scrollTop = chatBox.scrollHeight;
    })
    .catch(error => {
        hideTypingIndicator();
        console.error('Error:', error);
    });
}

function appendMessage(sender, message) {
    let chatBox = document.getElementById("chat-box");
    let messageDiv = document.createElement("div");
    messageDiv.className = "chat-message " + (sender === "Yumiko" ? "bot-message" : "user-message");
    messageDiv.innerHTML = `<strong>${sender}:</strong> ${message}`;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function showTypingIndicator() {
    let chatBox = document.getElementById("chat-box");

    // Remove any existing typing indicators
    hideTypingIndicator();

    // Create typing indicator
    let typingIndicator = document.createElement("div");
    typingIndicator.className = "chat-message bot-message typing-indicator";
    typingIndicator.innerHTML = `
        <div class="typing-indicator-bubble">
            <div class="typing-indicator-dot"></div>
            <div class="typing-indicator-dot"></div>
            <div class="typing-indicator-dot"></div>
        </div>
    `;

    chatBox.appendChild(typingIndicator);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function hideTypingIndicator() {
    let existingIndicators = document.getElementsByClassName("typing-indicator");
    Array.from(existingIndicators).forEach(indicator => indicator.remove());
}
