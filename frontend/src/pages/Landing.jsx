import { Button } from "@/components/ui/button";
import { useTheme } from "@/context/ThemeContext";
import { ChevronRight, Brain, Target, TrendingUp, Zap, Moon, Sun } from "lucide-react";

const Landing = () => {
  const { theme, toggleTheme } = useTheme();

  const handleLogin = () => {
    // Redirect to auth callback page after Google OAuth
    const redirectUrl = window.location.origin + '/auth/callback';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const features = [
    {
      icon: Brain,
      title: "AI That Remembers",
      description: "Your coach remembers your mistakes from weeks ago. It builds a complete picture of your weaknesses."
    },
    {
      icon: Target,
      title: "Pattern Recognition",
      description: "Identifies recurring mistakes like missed pins, center control issues, and one-move blunders."
    },
    {
      icon: TrendingUp,
      title: "Human Commentary",
      description: "No engine-speak. Just clear, actionable advice in plain language."
    },
    {
      icon: Zap,
      title: "Import From Anywhere",
      description: "Connect Chess.com and Lichess to automatically import and analyze your games."
    }
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <span className="text-primary-foreground font-bold text-sm">E1</span>
              </div>
              <span className="font-bold text-lg tracking-tight">Chess Coach</span>
            </div>
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                data-testid="theme-toggle"
              >
                {theme === "dark" ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </Button>
              <Button 
                onClick={handleLogin}
                data-testid="login-button"
                className="glow-primary"
              >
                Get Started
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section - Tetris Grid */}
      <main className="pt-16">
        <section className="relative min-h-[90vh] flex items-center overflow-hidden">
          {/* Background Image */}
          <div 
            className="absolute inset-0 z-0"
            style={{
              backgroundImage: `url(https://images.unsplash.com/photo-1642056877252-7823a86b9f9e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzZ8MHwxfHNlYXJjaHwzfHxjaGVzcyUyMGJvYXJkJTIwY2xvc2UlMjB1cCUyMG1hY3JvfGVufDB8fHx8MTc3MDA1NzE0OXww&ixlib=rb-4.1.0&q=85)`,
              backgroundSize: 'cover',
              backgroundPosition: 'center'
            }}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-background via-background/95 to-background/60 dark:from-background dark:via-background/90 dark:to-transparent" />
          </div>

          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
              {/* Hero Content - Col span 8 */}
              <div className="lg:col-span-7 space-y-8">
                <div className="space-y-4 animate-fadeIn">
                  <p className="text-sm uppercase tracking-widest text-primary font-medium">
                    AI-Powered Chess Coaching
                  </p>
                  <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-tight">
                    Your Personal
                    <span className="text-primary"> Grandmaster</span>
                    <br />
                    <span className="text-accent">Coach</span>
                  </h1>
                  <p className="text-lg sm:text-xl text-muted-foreground max-w-xl">
                    An AI coach that actually understands your playing style. 
                    It remembers your mistakes, recognizes patterns, and guides you 
                    like a human mentor would.
                  </p>
                </div>

                <div className="flex flex-col sm:flex-row gap-4 animate-fadeIn stagger-2">
                  <Button 
                    size="lg" 
                    onClick={handleLogin}
                    data-testid="hero-cta-button"
                    className="text-lg px-8 py-6 glow-primary"
                  >
                    Start Training Free
                    <ChevronRight className="w-5 h-5 ml-2" />
                  </Button>
                  <Button 
                    size="lg" 
                    variant="outline"
                    className="text-lg px-8 py-6"
                    data-testid="learn-more-button"
                    onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
                  >
                    Learn More
                  </Button>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-8 pt-8 animate-fadeIn stagger-3">
                  <div>
                    <p className="text-3xl font-bold text-primary">24/7</p>
                    <p className="text-sm text-muted-foreground">Always Available</p>
                  </div>
                  <div>
                    <p className="text-3xl font-bold text-accent">100%</p>
                    <p className="text-sm text-muted-foreground">Personalized</p>
                  </div>
                  <div>
                    <p className="text-3xl font-bold">∞</p>
                    <p className="text-sm text-muted-foreground">Game Imports</p>
                  </div>
                </div>
              </div>

              {/* Hero Visual - Col span 4 */}
              <div className="lg:col-span-5 hidden lg:block">
                <div className="relative">
                  <div className="absolute -inset-4 bg-primary/20 rounded-3xl blur-3xl" />
                  <div className="relative glass rounded-2xl p-6 space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                        <Brain className="w-5 h-5 text-primary" />
                      </div>
                      <div>
                        <p className="font-medium text-sm">AI Coach</p>
                        <p className="text-xs text-muted-foreground">Analyzing your game...</p>
                      </div>
                    </div>
                    <div className="space-y-3 font-mono text-sm">
                      <div className="p-3 rounded-lg bg-background/50">
                        <p className="text-muted-foreground mb-1">Move 15: Nd5</p>
                        <p className="text-foreground">"Remember the pinning issue we discussed last week? This knight is pinned to your queen. Look for the bishop check first."</p>
                      </div>
                      <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                        <p className="text-red-400 text-xs uppercase tracking-wide mb-1">Pattern Detected</p>
                        <p className="text-foreground text-sm">This is your 3rd missed pin in 5 games.</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section id="features" className="py-24 bg-card/50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-16">
              <p className="text-sm uppercase tracking-widest text-primary font-medium mb-4">
                Features
              </p>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
                Not Just Analysis.
                <br />
                <span className="text-primary">Real Coaching.</span>
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {features.map((feature, index) => (
                <div 
                  key={feature.title}
                  className={`p-6 rounded-xl bg-card border border-border/50 hover:border-primary/50 transition-all duration-300 hover:shadow-lg animate-fadeIn stagger-${index + 1}`}
                  data-testid={`feature-card-${index}`}
                >
                  <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                    <feature.icon className="w-6 h-6 text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                  <p className="text-muted-foreground text-sm">{feature.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-24 relative overflow-hidden">
          <div 
            className="absolute inset-0 z-0 opacity-20"
            style={{
              backgroundImage: `url(https://images.unsplash.com/photo-1642262798341-50fde182ebf5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDN8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMG5ldXJhbCUyMG5ldHdvcmslMjBnbG93aW5nJTIwYmx1ZSUyMGdvbGQlMjB0ZWNobm9sb2d5fGVufDB8fHx8MTc3MDA1NzExM3ww&ixlib=rb-4.1.0&q=85)`,
              backgroundSize: 'cover',
              backgroundPosition: 'center'
            }}
          />
          <div className="relative z-10 max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-6">
              Ready to Improve Your Game?
            </h2>
            <p className="text-lg text-muted-foreground mb-8">
              Import your games from Chess.com or Lichess and get personalized coaching today.
            </p>
            <Button 
              size="lg" 
              onClick={handleLogin}
              data-testid="cta-button"
              className="text-lg px-8 py-6 glow-primary"
            >
              Start Free with Google
              <ChevronRight className="w-5 h-5 ml-2" />
            </Button>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/50 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-primary flex items-center justify-center">
                <span className="text-primary-foreground font-bold text-xs">E1</span>
              </div>
              <span className="text-sm text-muted-foreground">Chess Coach</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Built with AI. Made for chess players.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
