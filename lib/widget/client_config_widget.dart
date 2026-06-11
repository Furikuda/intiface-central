import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intiface_central/bloc/configuration/intiface_configuration_cubit.dart';
import 'package:intiface_central/bloc/engine/engine_control_bloc.dart';
import 'package:intiface_central/util/docs_screenshot_keys.dart';
import 'package:flutter_settings_ui/flutter_settings_ui.dart';

class ClientConfigWidget extends StatefulWidget {
  const ClientConfigWidget({super.key});

  @override
  State<ClientConfigWidget> createState() => _ClientConfigWidgetState();
}

class _ClientConfigWidgetState extends State<ClientConfigWidget> {
  late TextEditingController _clientAddressController;

  @override
  void initState() {
    super.initState();
    _clientAddressController = TextEditingController();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    var configCubit = BlocProvider.of<IntifaceConfigurationCubit>(context);
    _clientAddressController.text = configCubit.clientWebsocketAddress;
  }

  @override
  void dispose() {
    _clientAddressController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: BlocBuilder<EngineControlBloc, EngineControlState>(
        buildWhen: ((previous, current) =>
            current is EngineStartedState || current is EngineStoppedState),
        builder: (context, engineState) {
          return BlocBuilder<
            IntifaceConfigurationCubit,
            IntifaceConfigurationState
          >(
            buildWhen: (previousState, currentState) =>
                currentState is ClientWebsocketAddressState,
            builder: (context, state) {
              var cubit = BlocProvider.of<IntifaceConfigurationCubit>(context);
              var engineIsRunning = BlocProvider.of<EngineControlBloc>(
                context,
              ).isRunning;
              List<AbstractSettingsSection> tiles = [
                SettingsSection(
                  title: _settingsText("Client Settings"),
                  tiles: [
                    SettingsTile.navigation(
                      enabled: !engineIsRunning,
                      title: _settingsText("Remote Server Address"),
                      value: _settingsText(cubit.clientWebsocketAddress),
                      onPressed: (context) {
                        showDialog(
                          context: context,
                          builder: (context) => AlertDialog(
                            title: const Text('Remote Server Address'),
                            content: TextField(
                              controller: _clientAddressController,
                              onSubmitted: (value) {
                                cubit.clientWebsocketAddress = value;
                                Navigator.pop(context);
                              },
                              decoration: const InputDecoration(
                                hintText: "ws://host:port",
                              ),
                            ),
                            actions: <Widget>[
                              TextButton(
                                onPressed: () =>
                                    Navigator.pop(context, 'Cancel'),
                                child: const Text('Cancel'),
                              ),
                              TextButton(
                                onPressed: () {
                                  cubit.clientWebsocketAddress =
                                      _clientAddressController.text;
                                  Navigator.pop(context);
                                },
                                child: const Text('OK'),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ],
                ),
              ];
              return SettingsList(
                key: DocsScreenshotKeys.appModeSettingsBody,
                sections: tiles,
              );
            },
          );
        },
      ),
    );
  }
}

const _settingsTextStyle = TextStyle(fontFamily: 'Roboto');

Text _settingsText(String text) {
  return Text(text, style: _settingsTextStyle);
}
