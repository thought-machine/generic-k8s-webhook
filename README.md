# generic-k8s-webhook

Configurable K8S webhook that can implement multiple validators and mutators using a simple yaml config file.

For example, this file configures it to validate that no `serviceaccount` is uses the `kube-system` namespace. This validator can be accessed on `<hostname>:<port>/check-namespace-sa`.

```yaml
apiVersion: generic-webhook/v1alpha1
kind: GenericWebhookConfig
webhooks:
  - name: check-namespace-sa
    path: /check-namespace-sa
    actions:
      # Refuse the request if it's a ServiceAccount that
      # is placed on the "kube-system" namespace
      - condition:
          and:
            - equal:
                - getValue: .metadata.namespace
                - const: kube-system
            - equal:
                - getValue: .kind
                - const: ServiceAccount
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
    apiVersion: generic-webhook/v1alpha1
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
apiVersion: generic-webhook/v1alpha1
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

The syntax of the `condition` can be found in [Defining a condition](#defining-a-condition). The syntax of the patch can be found in [Defining a patch](#defining-a-patch).

### Testing the `GenericWebhookConfig` file is correct

It can be frustrating to deploy a change in the `configmap` that contains the `GenericWebhookConfig` just to see that it's not working as expected. For this reason, it's advisable to test new configurations in advance. That's why this app can be invoked as a cli tool.

Assuming you've cloned the repo and you have [poetry](https://python-poetry.org/docs/) installed.

```bash
poetry run python3 generic_k8s_webhook/main.py --config <path-to-GenericWebhookConfig-file> cli --k8s-manifest <k8s-manifest-to-analise> --wh-name <webhook-to-use>
```

The value of the `--config` argument is the path of the `GenericWebhookConfig` config file. The value of the `--k8s-manifest` argument is a K8S manifest file that will be processed by the webhook. The value of the `--wh-name` is just the name of the webhook that we'll use to process the manifest. Remember that we can have several webhooks in the same app.

### Defining a condition

When defining a condition, we can use any of the following operators.

- [const](#const)
- [getValue](#getvalue)
- [and](#and)
- [or](#or)
- [not](#not)
- [equal](#equal)
- [sum](#sum)
- [forEach](#foreach)

#### const

Defines a constant value. It is normally used with the [equal](#equal) operator, in case we want to check that a field in the manifest equals to a value that we define (using the `const` operator).

```yaml
const: <constant value>
```

#### getValue

Retrieves a value defined in the manifest. The `<path>` is a `.` (dot) separated path that references a field in the manifest. For example, `.metadata.name`. If the `getValue` is used nested within the [forEach](#foreach) operator, by default it will take as a base context the item that the [forEach](#foreach) is iterating. If you want to use the root of the manifest as the context, then you must add a `$` at the beginning of the path. For example, `$.metadata.name` will always resolve to the metadata defined at the root level independently if the `getValue` is nested in a [forEach](#foreach) or not.

```yaml
# Refers to the latest context
getValue: .metadata.name

# Refers always to the root context
getValue: $.metadata.name
```

#### and

It performs an `and` operation on a list of elements. The list of elements can be explicitly defined (an actual yaml list) or implicitly defined. This last case is exemplified when the `and` consumes the result generated by the [forEach](#foreach) operator.

```yaml
and:
  - <elem1>
  - <elem2>
  - ...

and:
  forEach:
    ...
```

#### or

It performs an `or` operation on a list of elements. The list of elements can be explicitly defined (an actual yaml list) or implicitly defined. This last case is exemplified when the `or` consumes the result generated by the [forEach](#foreach) operator.

```yaml
or:
  - <elem1>
  - <elem2>
  - ...

or:
  forEach:
    ...
```

#### not

It negates the value of its argument.

```yaml
not:
  <operator>

not:
  and:
    - ...
```

#### equal

Compares two elements and returns true if they are equal.

```yaml
equal:
  - const: default
  - getValue: .metadata.namespace
```

#### sum

Sums the values of a list of elements. The list of elements can be explicitly defined (an actual yaml list) or implicitly defined. This last case is exemplified when the `sum` consumes the result generated by the [forEach](#foreach) operator.

```yaml
sum:
  - const: 1
  - const: 4

sum:
  forEach:
    ...
```

#### forEach

It's like a `map` operation. If executes the operation `op` for each element defined in `elements`. It returns the transformed list of elements. The [getValue](#getvalue) operator that lives within a `forEach` receives as context the current element that the `forEach` is iterating. In this example, `.name` resolves to the name of a container.

```yaml
forEach:
  elements: {getValue: .spec.containers}
  op:
    equal:
      - const: my-side-car
      - getValue: .name
```

### Defining a patch

The patch is defined almost in the same as a standard [jsonpatch](https://jsonpatch.com/). The only difference is that, when defining a path, instead of using `/` to separate its components, we use `.`.

```yaml
patch:
  - op: add
    path: .metadata.labels
    value: <any value>
```

## Contributing

See the [contributor guide](./docs/contributor-guide.md)
