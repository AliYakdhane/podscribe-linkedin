import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

export interface PodcastConfig {
  show_id: string;
  apple_episode_url: string;
  max_episodes_per_run: number;
}

export interface Transcript {
  guid: string;
  title: string;
  published_at?: string;
  created_at?: string;
  transcript_content: string;
}

export interface Post {
  id?: number;
  guid: string;
  title: string;
  published_at?: string;
  posts_content?: string;
  post_type: string;
  created_at?: string;
}

export interface PullStatus {
  output: string;
  success: boolean;
  config_id: string | null;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(
    private http: HttpClient,
    private auth: AuthService
  ) {
    // eslint-disable-next-line no-console
    console.log('ApiService: using apiUrl', environment.apiUrl);
  }

  private options() {
    return { headers: this.auth.authHeaders() };
  }

  getConfig(configId: 'apple' | 'second_podcast' | 'twiml' | 'practical_ai' | 'a16z' | 'cognitive_rev' | 'hard_fork' | 'lex_fridman' | 'dwarkesh' | 'nvidia_ai'): Observable<PodcastConfig> {
    return this.http.get<PodcastConfig>(
      `${environment.apiUrl}/api/config/${configId}`,
      this.options()
    );
  }

  putConfig(configId: 'apple' | 'second_podcast' | 'twiml' | 'practical_ai' | 'a16z' | 'cognitive_rev' | 'hard_fork' | 'lex_fridman' | 'dwarkesh' | 'nvidia_ai', body: PodcastConfig): Observable<{ success: boolean }> {
    return this.http.put<{ success: boolean }>(
      `${environment.apiUrl}/api/config/${configId}`,
      body,
      this.options()
    );
  }

  runPull(configId: string, showId?: string, appleEpisodeUrl?: string, runLimit: number = 10): Observable<{ success: boolean; config_id: string }> {
    return this.http.post<{ success: boolean; config_id: string }>(
      `${environment.apiUrl}/api/pull/run`,
      { config_id: configId, show_id: showId, apple_episode_url: appleEpisodeUrl, run_limit: runLimit },
      this.options()
    );
  }

  runPullAll(): Observable<{ success: boolean; config_id: string }> {
    return this.http.post<{ success: boolean; config_id: string }>(
      `${environment.apiUrl}/api/pull/run-all`,
      {},
      this.options()
    );
  }

  getPullStatus(): Observable<PullStatus> {
    return this.http.get<PullStatus>(
      `${environment.apiUrl}/api/pull/status`,
      this.options()
    );
  }

  getTranscripts(configId?: 'apple' | 'second_podcast' | 'twiml' | 'practical_ai' | 'a16z' | 'cognitive_rev' | 'hard_fork' | 'lex_fridman' | 'dwarkesh' | 'nvidia_ai'): Observable<Transcript[]> {
    let params = new HttpParams();
    if (configId) {
      params = params.set('config_id', configId);
    }
    return this.http.get<Transcript[]>(
      `${environment.apiUrl}/api/transcripts`,
      { ...this.options(), params }
    );
  }

  getPosts(): Observable<Post[]> {
    return this.http.get<Post[]>(
      `${environment.apiUrl}/api/posts`,
      this.options()
    );
  }

  generateLinkedIn(transcriptGuid: string, transcriptTitle: string, publishedAt: string, voice: string, instructions: string): Observable<{ posts: string[]; saved: boolean }> {
    return this.http.post<{ posts: string[]; saved: boolean }>(
      `${environment.apiUrl}/api/generate/linkedin`,
      {
        transcript_guid: transcriptGuid,
        transcript_title: transcriptTitle,
        published_at: publishedAt || undefined,
        voice,
        instructions,
      },
      this.options()
    );
  }

  generateBlog(transcriptGuid: string, transcriptTitle: string, publishedAt: string, voice: string, instructions: string): Observable<{ blog: Record<string, unknown>; saved: boolean }> {
    return this.http.post<{ blog: Record<string, unknown>; saved: boolean }>(
      `${environment.apiUrl}/api/generate/blog`,
      {
        transcript_guid: transcriptGuid,
        transcript_title: transcriptTitle,
        published_at: publishedAt || undefined,
        voice,
        instructions,
      },
      this.options()
    );
  }
}
