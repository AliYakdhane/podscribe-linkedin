import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent implements OnInit {
  username = 'admin';
  password = '';
  loading = false;
  error = '';

  constructor(
    private auth: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    if (this.auth.isAuthenticated()) this.router.navigate(['/']);
  }

  onSubmit(): void {
    this.error = '';
    this.loading = true;
    this.auth.login(this.username, this.password).subscribe({
      next: (res: any) => {
        this.loading = false;
        if (res?.success) this.router.navigate(['/']);
        else this.error = res?.message || (Array.isArray(res?.detail) ? res.detail[0]?.msg : res?.detail) || 'Login failed';
      },
      error: () => {
        this.loading = false;
        this.error = 'Login failed';
      },
    });
  }
}
