# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e3]:
    - generic [ref=e5]:
      - generic [ref=e6]:
        - generic [ref=e8]: Step 1 of 2
        - generic [ref=e12]: Link Your Chess Account
        - generic [ref=e13]: Connect at least one account to analyze your games
      - generic [ref=e14]:
        - generic [ref=e15]:
          - text: Chess.com Username
          - generic [ref=e16]:
            - textbox "Chess.com Username" [ref=e17]:
              - /placeholder: Enter your Chess.com username
            - button [disabled]:
              - img
        - generic [ref=e20]: OR
        - generic [ref=e22]:
          - text: Lichess Username
          - generic [ref=e23]:
            - textbox "Lichess Username" [ref=e24]:
              - /placeholder: Enter your Lichess username
            - button [disabled]:
              - img
        - generic [ref=e25]:
          - button "Continue" [disabled]:
            - text: Continue
            - img
          - button "Explore Demo Mode Instead" [ref=e26] [cursor=pointer]
    - region "Notifications alt+T"
  - link "Made with Emergent" [ref=e27] [cursor=pointer]:
    - /url: https://app.emergent.sh/?utm_source=emergent-badge
    - img [ref=e28]
    - paragraph [ref=e31]: Made with Emergent
```