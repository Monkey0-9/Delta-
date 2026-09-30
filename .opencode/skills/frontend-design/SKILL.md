---
name: frontend-design
description: Use when building UI layouts, design systems, or responsive interfaces with modern frontend tools.
---

# Frontend Design

## When to Use This Skill
- Building or modifying frontend UI and layouts
- Implementing responsive design for mobile, tablet, and desktop
- Creating accessible interfaces that meet WCAG standards
- Prototyping with Tailwind CSS or CSS custom properties
- Adding animations and transitions to UI components

## Workflow
1. Analyze the UI requirements: components, breakpoints, and interaction patterns
2. Define the layout structure: grid or flexbox, container widths, spacing
3. Implement the base styles: reset, typography, color tokens
4. Build components from the outside in: container → row → cell → content
5. Add responsive behavior: media queries or container queries for each breakpoint
6. Implement interactions: hover states, focus rings, transitions
7. Validate accessibility: semantic HTML, ARIA labels, keyboard navigation, color contrast
8. Test across browsers and devices

## Rules
- Prioritize accessibility — use semantic HTML before ARIA
- Design mobile-first — start with the smallest screen and scale up
- Use consistent spacing from a defined scale, not arbitrary values
- Ensure interactive elements have visible focus indicators
- Test with screen readers and keyboard-only navigation
- Avoid layout shift — reserve space for dynamic content
