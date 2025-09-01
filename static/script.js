// static/script.js

// Show alert when appointment is booked
function appointmentBooked() {
    alert("✅ Your appointment has been booked successfully!");
}

// Confirm before canceling an appointment
function confirmCancel() {
    return confirm("⚠️ Are you sure you want to cancel this appointment?");
}

// Confirm before confirming an appointment
function confirmApproval() {
    return confirm("Do you want to confirm this appointment?");
}