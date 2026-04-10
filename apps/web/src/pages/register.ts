import { register } from '../auth';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('userDetails');
    if (!form) return;

    form.addEventListener('submit', (e: Event) => {
        e.preventDefault();
        const email = (document.getElementById('email') as HTMLInputElement).value;
        const password = (document.getElementById('pwd') as HTMLInputElement).value;
        const confirmPassword = (document.getElementById('confirmPwd') as HTMLInputElement).value;
        register(email, password, confirmPassword);
    });
});
