console.log("JS Loaded");


var map = L.map('map').setView([17.3850, 78.4867], 10);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
}).addTo(map);

// LIVE LOCATION
var socket = io();

// SEND LOCATION
if (navigator.geolocation) {
    navigator.geolocation.watchPosition(position => {
        let lat = position.coords.latitude;
        let lng = position.coords.longitude;

        socket.emit("location", { lat: lat, lng: lng });
    });
}

// RECEIVE LOCATION
socket.on("location", function (data) {
    console.log("User location:", data.lat, data.lng);
});
// CHAT
function sendMessage(event, ride_id) {
    if (event.key === "Enter") {
        socket.emit("message", {
            ride_id: ride_id,
            message: event.target.value
        });
        event.target.value = "";
    }
}

socket.on("message", function (data) {
    let box = document.getElementById("chat-" + data.ride_id);
    box.innerHTML += "<div>" + data.message + "</div>";
});
document.addEventListener("DOMContentLoaded", function () {
    console.log("JS Ready");

    const chatIcon = document.getElementById("chat-icon");
    const chatBox = document.getElementById("chat-box");

    if (!chatIcon || !chatBox) {
        console.log("Chat elements not found");
        return;
    }

    chatIcon.addEventListener("click", function () {
        console.log("Icon clicked");

        if (chatBox.style.display === "block") {
            chatBox.style.display = "none";
        } else {
            chatBox.style.display = "block";
        }
    });
});
function sendChat(event) {
    if (event.key === "Enter") {
        let input = document.getElementById("chat-input");
        let message = input.value;

        let chat = document.getElementById("chat-messages");

        // show user message
        chat.innerHTML += `<div class="user-msg">${message}</div>`;

        fetch("/chatbot", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message: message})
        })
        .then(res => res.json())
        .then(data => {
            chat.innerHTML += `<div class="bot-msg">${data.response}</div>`;
            chat.scrollTop = chat.scrollHeight;
        });

        input.value = "";
    }
}
function clearChat() {
    if (confirm("Clear all chat messages?")) {
        document.getElementById("chat-messages").innerHTML = "";
    }
}
function openAbout() {
    document.getElementById("about-modal").classList.add("show");
}

function closeAbout() {
    document.getElementById("about-modal").classList.remove("show");
}