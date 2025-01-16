# generic-k8s-webhook

Configurable K8S webhook that can implement multiple validators and mutators using a simple yaml config file.

For example, this is the config to validate that no `serviceaccount` uses the `kube-system` namespace. This validator can be accessed on `<hostname>:<port>/check-namespace-sa`.

```yaml
apiVersion: generic-webhook/v1beta1
kind: GenericWebhookConfig
webhooks:
  - name: check-namespace-sa
    path: /check-namespace-sa
    actions:
      # Refuse the request if it's a ServiceAccount that
      # is placed on the "kube-system" namespace
      - condition: .metadata.namespace == "kube-system" && .kind == "ServiceAccount"
        accept: false
```

## Why should you use the `generic-k8s-webhook`?

With this project, you can **avoid writing from scratch simple K8S Validating or Mutating webhooks**. The logic of the webhook can be written in a simple yaml configuration file. Moreover, this **yaml config can be changed dynamically** without the need of restarting the app.

Apart from that, it also allows you to maintain **a single K8S deployment for all your webhooks** instead of having to maintain a separate deployment for each webhook. This is possible because the `GenericWebhookConfig` config file accepts multiple webhook configs, each listening to a different path.

## Deploying the generic webhook to K8S

You need (at least) the following resources:

- deployment
- service
- configmap

The `configmap` should contain the `GenericWebhookConfig`.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  [...]
data:
  generic-webhook-config: |
    apiVersion: generic-webhook/v1beta1
    kind: GenericWebhookConfig
    webhooks:
      - ...
      - ...
```

The pod template within the `deployment` should mount the previous config map as a file. Finally, in the same pod template, we should pass `--config <path-to-mounted-generic-webhook-config-file>` and `--port <port>` as `args` for the container.

## The `GenericWebhookConfig` config file

This file allows the user to configure several webhooks in a single app. In this section, we'll see the structure and syntax that it follows.

The [examples](./examples/) directory contains a fair amount of examples to help the user better understand how they can leverage the `GenericWebhookConfig` to write their own Validating or Mutating webhooks.

```yaml
apiVersion: generic-webhook/v1beta1
kind: GenericWebhookConfig
webhooks:
  - # Configuration for the first webhook

  - # Configuration for the second webhook

  ...
```

The structure of the configuration of a webhook (an entry in the `webhooks` list) is the following:

```yaml
# Name used to identify this webhook
name: <name>
# Path where this webhook will listen (<hostname>:<port>/<path>)
path: <path>
# The actions (accept and/or patch) this webhook will perform
actions:
  - # The condition that must be met to execute this action. The condition
    # is evaluated based on the K8S manifest that the K8S control plane sends
    # to this app.
    # For example, "the manifest defines a pod and this pod defines request.cpu"
    condition: {}
    # [ACTION] Whether to accept or not the manifest sent by the K8S control plane
    # If not specified, it defaults to true
    accept: true | false
    # [ACTION] The patch to apply to the manifest. If set, then the webhook behaves
    # as a Mutating webhook
    patch: []

  - ...

```

If more than one webhook have the same path, they will be called in order. The `accept` responses are ANDed and the `patch` responses are concatenated. Notice that a given webhook will receive the payload already modified by all the previous webhooks that have the same path.

The syntax of the `condition` can be found in [Defining a condition](#defining-a-condition). The syntax of the patch can be found in [Defining a patch](#defining-a-patch).

### Testing the `GenericWebhookConfig` file is correct

It can be frustrating to deploy a change in the `configmap` that contains the `GenericWebhookConfig` just to see that it's not working as expected. For this reason, it's advisable to test new configurations in advance. That's why this app can be invoked as a cli tool.

Assuming you've cloned the repo and you have [poetry](https://python-poetry.org/docs/) installed.

```bash
poetry run python3 generic_k8s_webhook/main.py --config <path-to-GenericWebhookConfig-file> cli --k8s-manifest <k8s-manifest-to-analise> --wh-name <webhook-to-use>
```

The value of the `--config` argument is the path of the `GenericWebhookConfig` config file. The value of the `--k8s-manifest` argument is a K8S manifest file that will be processed by the webhook. The value of the `--wh-name` is just the name of the webhook that we'll use to process the manifest. Remember that we can have several webhooks in the same app.

### Defining a condition

The conditions can be defined using structured operators and/or a simple pseudolanguage. For example, the following condition combines both a structured operator (an `and`) and a couple of lines of this pseudolanguage.

```yaml
and:
  - .kind == "Pod"
  - .metadata.labels.latencyCritical == true && .metadata.labels.app == "backend"
```

We can also iterate over lists and nested lists. In the following example, we check that a pod has at least one container called "main".

```yaml
any: .spec.containers.* -> .name == "main"
```

The `*` is used to iterate over a list, in that case the list of containers. The `->` operator is like a map. So, assuming the pod has two containers, one named "main" and the other named "foo", the `.spec.containers.* -> .name == "main"` returns `[true, false]`.

You can check [operators-reference](./docs/operators-reference.md) to see all the available structured operators.

### Defining a patch

The patch is defined almost in the same as a standard [jsonpatch](https://jsonpatch.com/). The only difference is that, when defining a path, instead of using `/` to separate its components, we use `.`.

```yaml
patch:
  - op: add
    path: .metadata.labels
    value: <any value>
```

## Next steps

- Script to measure performance (API calls per second) for a single replica
- Create a CRD for the `GenericWebhookConfig` and consume it as a K8S object instead of as a ConfigMap
- Add more examples
- Helm chart
- Analyse how much CPU and memory the app needs
- Prometheus metrics to show number of requests processed, succeeded, queued requests, time it takes to process a request, etc.

## Contributing

See the [contributor guide](./docs/contributor-guide.md)
