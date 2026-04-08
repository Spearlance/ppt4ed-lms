// Dev login card — displays test credentials on the login page
(function () {
	// Only run on the login page
	if (window.location.pathname !== '/login') return;

	var DEV_EMAIL = 'dev@test.com';
	var DEV_PASSWORD = 'password123';

	function createDevLoginCard() {
		var loginBox = document.querySelector('.page-card');
		if (!loginBox) return;

		var card = document.createElement('div');
		card.id = 'dev-login-card';
		card.innerHTML =
			'<div style="' +
				'margin-top: 1rem;' +
				'padding: 1rem 1.25rem;' +
				'background: #f0f9fc;' +
				'border: 1px solid #0b6685;' +
				'border-radius: 8px;' +
				'font-family: inherit;' +
				'font-size: 0.875rem;' +
			'">' +
				'<div style="' +
					'font-weight: 600;' +
					'color: #0b6685;' +
					'margin-bottom: 0.5rem;' +
					'font-size: 0.9rem;' +
				'">Dev Login</div>' +
				'<div style="color: #374151; margin-bottom: 0.25rem;">' +
					'<strong>Email:</strong> ' + DEV_EMAIL +
				'</div>' +
				'<div style="color: #374151; margin-bottom: 0.75rem;">' +
					'<strong>Password:</strong> ' + DEV_PASSWORD +
				'</div>' +
				'<button id="dev-login-btn" style="' +
					'background: #0b6685;' +
					'color: white;' +
					'border: none;' +
					'padding: 0.5rem 1rem;' +
					'border-radius: 6px;' +
					'cursor: pointer;' +
					'font-size: 0.875rem;' +
					'font-weight: 500;' +
					'width: 100%;' +
				'">Fill & Login</button>' +
			'</div>';

		loginBox.appendChild(card);

		document.getElementById('dev-login-btn').addEventListener('click', function () {
			var emailInput = document.getElementById('login_email');
			var passwordInput = document.getElementById('login_password');
			var loginBtn = document.querySelector('.btn-login');

			if (emailInput) emailInput.value = DEV_EMAIL;
			if (passwordInput) passwordInput.value = DEV_PASSWORD;

			// Trigger input events so Frappe picks up the values
			if (emailInput) emailInput.dispatchEvent(new Event('change', { bubbles: true }));
			if (passwordInput) passwordInput.dispatchEvent(new Event('change', { bubbles: true }));

			if (loginBtn) loginBtn.click();
		});
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', createDevLoginCard);
	} else {
		createDevLoginCard();
	}
})();
