import { Component, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../services/auth.service';
import { ApiService, PodcastConfig, Transcript, Post } from '../../services/api.service';

export type PodcastTab = 'apple' | 'second_podcast' | 'twiml' | 'practical_ai' | 'a16z' | 'cognitive_rev' | 'hard_fork' | 'lex_fridman' | 'dwarkesh' | 'nvidia_ai';

interface PodcastTabItem {
  id: PodcastTab;
  label: string;
}

interface TabCache {
  config?: PodcastConfig | null;
  transcripts?: Transcript[];
  posts?: Post[];
}

const PODCAST_TABS: PodcastTabItem[] = [
  { id: 'apple', label: 'The AI Daily Brief' },
  { id: 'second_podcast', label: 'Latent Space' },
  { id: 'twiml', label: 'TWIML AI' },
  { id: 'practical_ai', label: 'Practical AI' },
  { id: 'a16z', label: 'The a16z Show' },
  { id: 'cognitive_rev', label: 'Cognitive Revolution' },
  { id: 'hard_fork', label: 'Hard Fork' },
  { id: 'lex_fridman', label: 'Lex Fridman' },
  { id: 'dwarkesh', label: 'Dwarkesh' },
  { id: 'nvidia_ai', label: 'NVIDIA AI' },
];

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  currentPodcast = signal<PodcastTab>('apple');
  config = signal<PodcastConfig | null>(null);
  transcripts = signal<Transcript[]>([]);
  posts = signal<Post[]>([]);
  pullOutput = signal('');
  pullSuccess = signal(false);
  loading = signal(false);
  error = signal('');
  saving = signal(false);
  pulling = signal(false);
  pullingAll = signal(false);
  generating = signal(false);
  copyDone = signal(false);

  showId = '';
  appleUrl = '';
  maxEpisodes = 10;
  runLimit = 10;
  voice = 'Professional, friendly';
  instructions = '';
  selectedTranscript: Transcript | null = null;
  selectedTranscriptGuid = '';
  showMobileMenu = signal(false);

  readonly podcastTabs = PODCAST_TABS;
  private cache: Record<PodcastTab, TabCache | null> = PODCAST_TABS.reduce((acc, p) => ({ ...acc, [p.id]: null }), {} as Record<PodcastTab, TabCache | null>);

  constructor(
    public auth: AuthService,
    private api: ApiService
  ) {}

  ngOnInit(): void {
    this.loading.set(true);
    this.loadConfig();
    this.loadTranscripts();
    this.loadPosts();
    this.loadPullStatus();
  }

  setPodcast(p: PodcastTab): void {
    this.currentPodcast.set(p);
    this.showMobileMenu.set(false);
    const cached = this.cache[p];

    if (cached?.transcripts && cached.transcripts.length > 0) {
      // Instant display from cache, then refresh in background
      this.transcripts.set(cached.transcripts);
      this.selectedTranscript = cached.transcripts[0];
      this.selectedTranscriptGuid = cached.transcripts[0].guid;
      this.loading.set(false);
    } else {
      // No cache yet: clear and show spinner until fresh data loads
      this.selectedTranscript = null;
      this.selectedTranscriptGuid = '';
      this.transcripts.set([]);
      this.loading.set(true);
    }

    // Always reload config + posts + transcripts (transcripts may be a fast refresh)
    this.loadConfig();
    this.loadTranscripts();
    this.loadPosts();
  }

  loadConfig(): void {
    const tab = this.currentPodcast();
    this.api.getConfig(tab).subscribe({
      next: (c) => {
        if (!this.cache[tab]) this.cache[tab] = {};
        this.cache[tab]!.config = c;
        if (this.currentPodcast() === tab) {
          this.config.set(c);
          this.showId = c?.show_id ?? '';
          this.appleUrl = c?.apple_episode_url ?? '';
          this.maxEpisodes = c?.max_episodes_per_run ?? 10;
        }
        this.error.set('');
      },
      error: () => {
        this.error.set('Failed to load config');
      },
    });
  }

  saveConfig(): void {
    this.saving.set(true);
    this.api.putConfig(this.currentPodcast(), {
      show_id: this.showId,
      apple_episode_url: this.appleUrl,
      max_episodes_per_run: this.maxEpisodes,
    }).subscribe({
      next: () => {
        this.saving.set(false);
        this.error.set('');
      },
      error: () => {
        this.saving.set(false);
        this.error.set('Failed to save');
      },
    });
  }

  runPull(): void {
    this.pulling.set(true);
    this.api.runPull(
      this.currentPodcast(),
      this.showId || undefined,
      this.appleUrl || undefined,
      this.runLimit
    ).subscribe({
      next: () => {
        this.pulling.set(false);
        setTimeout(() => this.loadPullStatus(), 2000);
      },
      error: (e) => {
        this.pulling.set(false);
        this.error.set(e.error?.detail || 'Pull failed');
      },
    });
  }

  runPullAll(): void {
    this.pullingAll.set(true);
    this.api.runPullAll().subscribe({
      next: () => {
        this.pullingAll.set(false);
        setTimeout(() => this.loadPullStatus(), 2000);
      },
      error: (e) => {
        this.pullingAll.set(false);
        this.error.set(e.error?.detail || 'Run all failed');
      },
    });
  }

  loadPullStatus(): void {
    this.api.getPullStatus().subscribe({
      next: (s) => {
        this.pullOutput.set(s.output);
        this.pullSuccess.set(s.success);
      },
    });
  }

  loadTranscripts(): void {
    const tab = this.currentPodcast();
    this.api.getTranscripts(tab).subscribe({
      next: (t) => {
        if (!this.cache[tab]) this.cache[tab] = {};
        this.cache[tab]!.transcripts = t;
        if (this.currentPodcast() === tab) {
          this.transcripts.set(t);
          if (t.length > 0) {
            this.selectedTranscript = t[0];
            this.selectedTranscriptGuid = t[0].guid;
          } else {
            this.selectedTranscript = null;
            this.selectedTranscriptGuid = '';
          }
        }
        this.loading.set(false);
      },
      error: () => {
        if (this.currentPodcast() === tab) this.transcripts.set([]);
        this.loading.set(false);
      },
    });
  }

  loadPosts(): void {
    const tab = this.currentPodcast();
    this.api.getPosts().subscribe({
      next: (p) => {
        if (!this.cache[tab]) this.cache[tab] = {};
        this.cache[tab]!.posts = p;
        if (this.currentPodcast() === tab) this.posts.set(p);
      },
      error: () => {
        if (this.currentPodcast() === tab) this.posts.set([]);
      },
    });
  }

  selectTranscript(t: Transcript): void {
    this.selectedTranscript = t;
    this.selectedTranscriptGuid = t?.guid ?? '';
  }

  onSelectTranscriptGuid(guid: string): void {
    this.selectedTranscriptGuid = guid;
    this.selectedTranscript = this.transcripts().find((x) => x.guid === guid) ?? null;
  }

  copyTranscript(): void {
    if (!this.selectedTranscript?.transcript_content) return;
    navigator.clipboard.writeText(this.selectedTranscript.transcript_content).then(() => {
      this.copyDone.set(true);
      setTimeout(() => this.copyDone.set(false), 2000);
    }).catch(() => {});
  }

  /** Format date for display (e.g. "March 11 - 2025") */
  formatTranscriptDate(t: Transcript): string {
    const raw = t.published_at || t.created_at || '';
    if (!raw) return 'Unknown date';
    try {
      const s = raw.replace('Z', '+00:00');
      const d = new Date(s);
      if (isNaN(d.getTime())) return raw;
      const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
      return `${months[d.getMonth()]} - ${d.getDate()} - ${d.getFullYear()}`;
    } catch {
      return raw;
    }
  }

  /** Truncate title for list display */
  transcriptListLabel(t: Transcript): string {
    const title = t.title.length > 60 ? t.title.slice(0, 57) + '...' : t.title;
    return `${title} (${this.formatTranscriptDate(t)})`;
  }

  generateLinkedIn(): void {
    if (!this.selectedTranscript) return;
    this.generating.set(true);
    this.api.generateLinkedIn(
      this.selectedTranscript.guid,
      this.selectedTranscript.title,
      this.selectedTranscript.published_at || '',
      this.voice,
      this.instructions
    ).subscribe({
      next: () => {
        this.generating.set(false);
        this.loadPosts();
      },
      error: () => this.generating.set(false),
    });
  }

  generateBlog(): void {
    if (!this.selectedTranscript) return;
    this.generating.set(true);
    this.api.generateBlog(
      this.selectedTranscript.guid,
      this.selectedTranscript.title,
      this.selectedTranscript.published_at || '',
      this.voice,
      this.instructions
    ).subscribe({
      next: () => {
        this.generating.set(false);
        this.loadPosts();
      },
      error: () => this.generating.set(false),
    });
  }

  linkedinPosts = computed(() => this.posts().filter((p) => p.post_type === 'linkedin'));
  blogPosts = computed(() => this.posts().filter((p) => p.post_type === 'blog'));
}
