import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../environments/environment';
import { tap, catchError, of } from 'rxjs';

export interface LoginResponse {
  success: boolean;
  token?: string;
  message?: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private token = signal<string | null>(localStorage.getItem('podcast_token'));
  isAuthenticated = computed(() => !!this.token());

  constructor(
    private http: HttpClient,
    private router: Router
  ) {}

  getToken(): string | null {
    return this.token();
  }

  login(username: string, password: string) {
    return this.http
      .post<LoginResponse>(`${environment.apiUrl}/api/auth/login`, { username, password })
      .pipe(
        tap((res) => {
          if (res.success && res.token) {
            localStorage.setItem('podcast_token', res.token);
            this.token.set(res.token);
          }
        }),
        catchError((err) => of(err.error ?? { success: false, message: err.message }))
      );
  }

  logout(): void {
    localStorage.removeItem('podcast_token');
    this.token.set(null);
    this.router.navigate(['/login']);
  }

  authHeaders(): { [key: string]: string } {
    const t = this.token();
    return t ? { Authorization: `Bearer ${t}` } : {};
  }
}
