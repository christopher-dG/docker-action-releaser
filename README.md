# Docker Action Releaser

Docker Action Releaser keeps your GitHub Action's Docker tags in sync with its Git tags.

Best practices dictate that you should tag releases of your project according to [SemVer](https://semver.org)
That's not very difficult, but there are a few moving parts to container actions that you want to keep in sync.
They are:

- The latest Git tag (`vX.Y.Z`, `latest`)
- The major, and minor Git tags (`vX.Y`, `vX`)
- The latest published Docker image (`X.Y.Z`, `latest`)
- The major and minor Docker tags (`X.Y`, `X`)
- The Docker image version referenced in `action.yml` (`X.Y.Z`)

This is the ideal situation for your users because it allows them to choose how they receive updates.
They can choose to lock themselves to specific patch release by using `your/action@v1.2.3`, receive patch updates with `your/action@v1.2`, or receive minor version bumps with `your/action@v1`, or even disregard SemVer altogether and stay on the most recent release with `your/action@latest`.

But maintaining this setup manually is not fun.
On every release, you'll need to:

- Update your `action.yml` file
- Create and push up to 4 Docker tags
- Create and push up to 4 Git tags

It's easy to skip a step, and it can have serious consequences (I created this action the day after botching a release of another one and causing hundereds of users to receive failure emails).

### Who Can Use

This action is for developers of container actions.
Your repository must have a `Dockerfile` at the top level, and your `action.yml` must have a section that looks like this:

```yml
runs:
  using: docker
  image: docker://my/repo:0
```

In this case, `my/repo` is any [Docker Hub](hub.docker.com) repository that you have push access to.
The starting version can be anything that is valid according to SemVer, with the addition that a missing minor or patch component is assumed to be `0` instead of making the whole thing invalid.

### How To Use

Create a workflow file at `.github/workflows/dar.yml`:

```yml
name: Docker Action Releaser
on:
  issue_comment:
    types: created
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: christopher-dG/docker-action-releaser@v1
        if: contains(github.event.comment.body, '/release')
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          docker_username: ${{ secrets.DOCKER_USERNAME }}
          docker_password: ${{ secrets.DOCKER_PASSWORD }}
```

Create a dummy issue like [this one](../../issues/1), and add a comment to it like this:

```
/release patch

Your optional release notes go here.
They get copied into the GitHub release.
```

The bump level can be "major", "minor", or "patch".
